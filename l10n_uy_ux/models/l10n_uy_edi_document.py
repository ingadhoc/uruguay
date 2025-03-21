import logging

from odoo import _, api, models

from odoo.exceptions import UserError
from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)


class L10nUyEdiDocument(models.Model):

    _inherit = "l10n_uy_edi.document"

    # Methods extend for l10n_uy_edi

    def action_update_dgi_state(self):
        # EXTEND l10n_uy_edi
        """ Permitimos actualizar estado solo si tenemos UUID y solo si esta en esperando respuesta.
        Si hay error no hay nada que consultar, y si fue aceptado rechazado ya no necesita ser actualizado """
        for doc in self.filtered(lambda x: x.move_id.move_type not in ['in_invoice', 'in_refund']):
            if not doc.uuid:
                raise UserError(_("Please return a 'UUID CFE Key' in order to continue"))
            if doc.state == "error":
                raise UserError(_("You can not obtain the invoice with errors"))
            if doc.state != "received":
                raise UserError(_("You can not update the state of a accepted/rejected invoice"))

        super().action_update_dgi_state()

    @api.model
    def _is_connection_info_incomplete(self, company):
        # EXTEND l10n_uy_edi
        """ Intenta mandar mensaje de error de alerta si estas en ambiente de testing con datos
        de producción

        Return:
            False if everything is ok,
            Message if there is a problem or something missing """
        res = super()._is_connection_info_incomplete(company)
        inbox_url = self._get_ws_url("inbox", company)
        query_url = self._get_ws_url("query", company)

        # Just in case they put production info in a testing environment by mistake
        if company.l10n_uy_edi_ucfe_env == "testing" and ("prod" in inbox_url or "prod" in query_url):
            res = (res or "") + _("Testing environment with production data. Please check/adjust the configuration")
        return res

    def _get_report_params(self):
        # EXTEND l10n_uy_edi
        """ Odoo oficial solo imprime el reporte standard de uruware.
        Aca extendemos para que haga dos cosas:

        1. Sirve para detectar si la adenda es muy grande automaticamente mandar a imprimir el reporte con adenda en
            hoja separada (si la adenda lleva > 6 lineas esto sucede)
        2. Sirve para enviar un reporte pre definido por el cliente en la configuracion de Odoo en lugar de imprimir
            el reporte por defecto de Uruware
        3.  En caso de que el documento sea un e-ticket o e-factura expo o sus respectivas NC y ND se fijara si
            el partner de la factura tiene definido algun lenguaje != español: de ser asi imprime el reporte tanto en
            español como en ingles (tambien es un formato disponible en uruware)
        """
        compatible_en = ['101', '102', '103', '121', '122', '123']
        adenda = self.move_id._l10n_uy_edi_get_addenda()
        report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or "[]")
        nombreParametros = report_params[0] if report_params else []
        valoresParametros = report_params[1] if report_params else []
        if adenda and len(adenda.splitlines()) > 6 and 'adenda' not in nombreParametros:
            nombreParametros.append('adenda')
            valoresParametros.append('true')
        if self.l10n_latam_document_type_id.code in compatible_en:
            if self.partner_id.lang and 'es' not in self.partner_id.lang and 'ingles' not in valoresParametros:
                nombreParametros.append('reporte')
                valoresParametros.append('ingles')
        elif 'ingles' in valoresParametros:
            nombreParametros.remove('reporte')
            valoresParametros.remove('ingles')

        if nombreParametros and valoresParametros:
            return "ObtenerPdfConParametros", {
                'nombreParametros': {"string": nombreParametros},
                'valoresParametros': {"string": valoresParametros}}
        return super()._get_report_params()

    # Metodos nuevos

    def ux_uy_get_last_invoice_number(self, document_type):
        """ Cuando la persona no tiene configurado para emitir el docuemnto en uruware deberia de saltarle
        este error. Necesitamos ver si lo agregamos a los check_moves

        El dia de mañana si quieremos un Consultar Comprobante de DGI podemos usar esto
        660 - Query to get next CFE number

        NOTE: This method take into account regular CFE documents (code < 200),
        does not take into account contingency documents

        With the document_type return the next number to be use for that document type.
        """
        # TODO este metodo esta implementado y funciona pero no lo estamos usando. tenemos dos opciones
        # 1. lo agregamos como un wizard similar a consultar ultimo DGI
        # 2. lo agregamos como parte de los checks, pero para ello necesitamos adaptarlo ya que no
        #    existe aun el edi_doc.
        self.ensure_one()
        res = False
        if int(document_type.code) != 0 and int(document_type.code) < 200:
            result = self._ucfe_inbox("660", {"TipoCfe": document_type.code})
            if errors := result.get("errors"):
                raise UserError(_(
                    "We were not able to get the info of the next invoice number: %(error)s", error=errors))

            response = result.get("response")
            if response is not None:
                next_number = response.findtext(".//{*}NumeroCfe", "")
                if not next_number:
                    raise UserError(_(
                        "You are not enabled to issue this document %(document)s, Please check your configuration settings",
                        document=document_type.display_name))
                res = int(next_number)
        return res
