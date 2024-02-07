# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.tools.safe_eval import safe_eval
from odoo.tools import safe_eval
from . import ucfe_errors


class L10nUyCfe(models.AbstractModel):

    _name = 'account.move'
    _inherit = ['account.move', 'l10n.uy.cfe']

    # TODO not sure if we needed
    # company_id = fields.Many2one("res.compaany")

    # TO remove via script
    """
    l10n_uy_cfe_state = fields.Selection([
        ('not_apply', 'Not apply - Not a CFE'),
        ('draft_cfe', 'Draft CFE'),
        # UCFE error states
        ('xml_error', 'ERROR: CFE XML not valid'),
        ('connection_error', 'ERROR: Connection to UCFE'),
        ('ucfe_error', 'ERROR: Related to UCFE'),
    """

    # Campos preparacion y acuseo de recepcion/envio xml

    l10n_uy_cfe_xml = fields.Text('XML CFE', copy=False, groups="base.group_system")
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")

    # Campos resultados almacenamiento de comprobantes emitidos

    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)
    l10n_uy_cfe_pdf = fields.Many2one('ir.attachment', string='CFE PDF Representation', copy=False)

    def set_any_extra_field(self, data):
        self.l10n_uy_cfe_xml = data.get('CfeXmlOTexto')
        transport = data.get('transport')
        self.l10n_uy_dgi_xml_response = transport.xml_response
        self.l10n_uy_dgi_xml_request = transport.xml_request

    def _get_report_params(self):
        """ En odoo ofical por defecto solo imprime el reporte standard de uruware.
        Aca lo extendemos para que haga dos cosas:

        1. Sirve para detectar si la adenda es muy grande automaticamente mandar a imprimir el reporte con adenda en hoja separada
        2. Sirve para enviar un reporte pre definido por el cliente en la configuracion de Odoo en lugar de imprimir el reporte por defecto de Uruware
        """
        # TODO: Aca tenemos un problema estamos revisando longitud de caracteres, pero en realidad debemos revisar es cantidad
        # de lineas que lleva la adenda, porque si es mayor que 6 lineas se corta
        addenda = self._l10n_uy_get_cfe_addenda()
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

    def action_l10n_uy_get_pdf(self):
        """ Solo permitir crear PDF cuando este aun no existe, y grabar en campo binario """
        # TODO toca poner a prueba
        self.ensure_one()
        if not self.l10n_uy_cfe_pdf:
            self.l10n_uy_cfe_pdf = self._l10n_uy_get_pdf()
        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=ir.attachment&id=" + str(self.l10n_uy_cfe_pdf.id) +
            "&filename_field=name&field=datas&download=true&name=" + self.l10n_uy_cfe_pdf.name,
            'target': 'self'
        }

    def action_l10n_uy_validate_cfe(self):
        """ Be able to validate a cfe """
        self.l10n_uy_edi_error = False
        self._l10n_uy_validate_cfe(self.sudo().l10n_uy_cfe_xml)

    def action_l10n_uy_preview_xml(self):
        """ Be able to show preview of the CFE to be send """
        self.l10n_uy_cfe_xml = self._l10n_uy_create_cfe().get('cfe_str')

    def _uy_prepare_req_data(self):
        self.ensure_one()
        req_data = super()._uy_prepare_req_data()
        req_data.update(self._l10n_uy_get_cfe_serie())
        return req_data

    def _l10n_uy_get_cfe_serie(self):
        """ Return dictionary with Serie CFE number.
        NOTE: In future need to be adapted for contigency records """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res

    def _l10n_uy_get_cfe_iddoc(self):
        res = super()._l10n_uy_get_cfe_iddoc()

        if self._is_uy_remito_type_cfe():  # A6
            res.update({'TipoTraslado': self.l10n_uy_transfer_of_goods})

        res.update(self._l10n_uy_get_cfe_serie())
        return res

    # def _uy_cfe_B24_MontoItem(self, line):
    # TODO en futuro para incluir descuentos B24 = (B9 * B11) - B13 + B17

    # TODO parece que tenemos estos tipos de contribuyente: IVA mínimo, Monotributo o Monotributo MIDES ver si cargarlos en el patner asi como la afip responsibility

    # def _uy_cfe_A41_RznSoc(self):
    # TODO company register name?

    # def _l10n_uy_get_cfe_receptor(self):
    # TODO -Free Shop: siempre se debe identificar al receptor.

    # A130 Monto Total a Pagar (NO debe ser reportado si de tipo remito u e-resguardo)
    # if not self._is_uy_remito_type_cfe() and not self._is_uy_resguardo():
    #     res['MntPagar'] = float_repr(self.amount_total, 2)
    #     # TODO Esto toca adaptarlo cuando agreguemos retenciones y percepciones ya que representa la
    #     # "Suma de (monto total + valor de la retención/percepción + monto no facturable)

    # def _uy_cfe_B4_IndFact(self, line):
    #     """ B4: Indicador de facturación

    #         TODO KZ: Toca revisar realmente cual es el line que corresponde, el que veo en la interfaz parece ser move_ids_without_package pero no se si esto siempre aplica
    #             move_ids_without_package	Stock moves not in package (stock.move)
    #             move_line_ids	Operations (stock.move.line)
    #             move_line_ids_without_package	Operations without package (stock.move.line)
    #     """

    # def _uy_cfe_A5_FchEmis(self):
    #     """ A5 FchEmis. Fecha del Comprobante """
    # return self.scheduled_date.strftime('%Y-%m-%d')
    # TODO KZ ver que fecha deberiamos de usar en caso de ser picking. opciones
    #   scheduled_date - Scheduled Date
    #   date - Creation Date
    #   date_deadline - Deadline
    #   date_done - Date of Transfer

    # def _uy_check_uy_invoices(self):
    # We check that there is one and only one vat tax per line
    # TODO KZ this could change soon, waiting functional confirmation
