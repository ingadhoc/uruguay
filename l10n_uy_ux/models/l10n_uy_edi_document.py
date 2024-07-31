
from odoo import _, api, fields, models

from odoo.exceptions import UserError
from odoo.tools import safe_eval
from odoo.addons.l10n_uy_edi.models import l10n_uy_edi_document


# TODO KZ revisar que esto funcione bien
l10n_uy_edi_document.RESPONSE_CODE_TO_STATE.update({
    "25": "rejected",  # Rechazado por DGI (Facturas de Proveedor)
})


class L10nUyEdiDocument(models.Model):
    _inherit = 'l10n_uy_edi.document'

    # Methods extend for l10n_uy_edi

    @api.model
    def _is_connection_info_incomplete(self, company):
        # EXTEND l10n_uy_edi
        """ Intenta mnadar mensaje de error de alerta si estas en ambiente de testing con datos
        de produccion

        Return:
            False if everything is ok,
            Message if there is a problem or something missing """
        res = super()._is_connection_info_incomplete(company)
        inbox_url = self._get_ws_url('inbox', company)
        query_url = self._get_ws_url('query', company)

        # Just in case they put production info in a testing environment by mistake
        if company.l10n_uy_edi_ucfe_env == 'testing' and ('prod' in inbox_url or 'prod' in query_url):
            res = (res or '') + _('Testing environment with production data. Please check/adjust the configuration')
        return res

    def _get_report_params(self):
        # EXTEND l10n_uy_edi
        """ Odoo oficial solo imprime el reporte standard de uruware.
        Aca extendemos para que haga dos cosas:

        1. Sirve para detectar si la adenda es muy grande automaticamente mandar a imprimir el reporte con adenda en hoja separada
        2. Sirve para enviar un reporte pre definido por el cliente en la configuracion de Odoo en lugar de imprimir el reporte por defecto de Uruware
        """
        # TODO: Aca tenemos un problema estamos revisando longitud de caracteres, pero en realidad debemos revisar es cantidad
        # de lineas que lleva la adenda, porque si es mayor que 6 lineas se corta
        addenda = self.move_id._l10n_uy_edi_get_addenda()
        if addenda and len(addenda) > 799:
            report_params = [['adenda'], ['true']]
        else:
            # En caso de que el cliente eliga el reporte que quiere imprimir
            report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or '[]')

        extra_params = {}
        if report_params:
            nombreParametros = report_params[0]
            valoresParametros = report_params[1]
            versionPdf = 'ObtenerPdfConParametros'
            extra_params.update({
                'nombreParametros': nombreParametros,
                'valoresParametros': valoresParametros,
            })
        else:
            versionPdf = 'ObtenerPdf'

        return versionPdf, extra_params

    def _get_cfe_tag(self):
        """ Agregamos el tag eResg. aun no lo usamos pero lo dejaamos disponible """
        self.ensure_one()
        if self._is_uy_resguardo():
            return 'eResg'
        return super()._get_cfe_tag()

    # def _l10n_uy_edi_check_invoices(self):
    # We check that there is one and only one vat tax per line
    # TODO KZ this could change soon, waiting functional confirmation

    # Metodos nuevos

    def _get_dgi_last_invoice_number(self, document_type):
        """ En este momento no lo usamos, en la version anterior lo usabamos para calcular la secuencia del proximo numero a usar.
        Realmente no era necesario y ya no lo hacemos, sin embargo quedo aca implementado.

        El dia de mañana si quieremos un Consultar Comprobante de DGI podemos usar esto que ya esta implementado
        ENDPOINT: 660 - Query to get next CFE number

        NOTE: This method take into account regular CFE documents (code < 200),
        does not take into account contingency documents

        With the document_type return the next number to be use for that document type.

        TODO KZ IMPORTANTE: Cuando la persona no tiene configurado para emitir el docuemnto en uruware deberia de saltarle este error.
        Necesitamos ver si lo agregamos a los check_moves """
        self.ensure_one()
        res = False
        if self.l10n_uy_edi_type == "electronic" and int(document_type.code) != 0 and int(document_type.code) < 200:
            result = self._ucfe_inbox("660", {"TipoCfe": document_type.code})
            if errors := result.get('errors'):
                raise UserError(_(
                    "We were not able to get the info of the next invoice number: %(error)s", error=errors))

        response = result.get('response')
        if response is not None:
            next_number = response.findtext(".//{*}NumeroCfe", "")
            if not next_number:
                raise UserError(_(
                    "You are not enabled to issue this document %(document)s, Please check your configuration settings",
                    document=document_type.display_name))
            res = int(next_number)
        return res

    # Methods related to vendor bill functionality

    # Metodos genericos que aun no se estarian usando mucho

    def _is_uy_resguardo(self):
        return self.l10n_latam_document_type_id.code in ['182', '282']

    def _l10n_uy_get_cfe_serie(self):
        """ Return dictionary with Serie CFE number.
        Si soy ticket de contingencia usar los valores que estan definidos en el Odoo

        NOTE: In future need to be adapted for contigency records """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res
