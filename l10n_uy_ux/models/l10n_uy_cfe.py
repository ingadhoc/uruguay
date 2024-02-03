# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models, api
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools import safe_eval


class L10nUyCfe(models.AbstractModel):

    _inherit = 'l10n.uy.cfe'

    # TODO KZ not sure if we needed
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

        # TODO KZ: Aca tenemos un problema estamos revisando longitud de caracteres, pero en realidad debemos revisar es cantidad
        # de lineas que lleva la adenda, porque si es mayor que 6 lineas se corta
        addenda = self._l10n_uy_get_cfe_addenda().get('Adenda')
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
        # TODO KZ toca poner a prueba
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
        self._l10n_uy_vaidate_cfe(self.sudo().l10n_uy_cfe_xml)

    def action_l10n_uy_preview_xml(self):
        """ Be able to show preview of the CFE to be send """
        self.l10n_uy_cfe_xml = self._l10n_uy_create_cfe().get('cfe_str')
