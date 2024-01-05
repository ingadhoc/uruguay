# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class ResCompany(models.Model):

    _inherit = "res.company"

    l10n_uy_ucfe_prod_env = fields.Text('Uruware Production Data', groups="base.group_system", default="{}")
    l10n_uy_ucfe_test_env = fields.Text('Uruware Testing Data', groups="base.group_system", default="{}")

    l10n_uy_report_params = fields.Char()

    # DGI
    l10n_uy_dgi_crt = fields.Binary(
        'DGI Certificate', groups="base.group_system", help="This certificate lets us"
        " connect to DGI to validate electronic invoice. Please upload here the DGI certificate in PEM format.")
    l10n_uy_dgi_crt_fname = fields.Char('DGI Certificate name')
    l10n_uy_dgi_crt_pass = fields.Char('Certificate Password')

    # @api.depends('l10n_uy_dgi_crt')
    # def _compute_l10n_uy_dgi_crt_fname(self):
    #     """ Set the certificate name in the company. Needed in unit tests, solved by a similar onchange method in
    #     res.config.settings while setting the certificate via web interface """
    #     with_crt = self.filtered(lambda x: x.l10n_uy_dgi_crt)
    #     remaining = self - with_crt
    #     for rec in with_crt:
    #         # certificate = self._l10n_uy_get_certificate_object(rec.l10n_uy_dgi_crt)
    #         # rec.l10n_uy_dgi_crt_fname = certificate.get_subject().CN
    #         rec.l10n_uy_dgi_crt_fname = ''

    # def _l10n_uy_get_certificate_object(self, cert):
    #     crt_str = base64.decodestring(cert).decode('ascii')
    #     res = crypto.load_certificate(crypto.FILETYPE_PEM, crt_str)
    #     import pdb; pdb.set_trace()
    #     return res

    def action_update_from_config(self):
        self.ensure_one()
        config = False
        if self.l10n_uy_ucfe_env == 'production':
            config = self.l10n_uy_ucfe_prod_env
        elif self.l10n_uy_ucfe_env == 'testing':
            config = self.l10n_uy_ucfe_test_env

        config = safe_eval(config or "{}")
        self.write(config)

    # TODO
    # Servicio para listados con autenticación en los cabezales SOAP
    # Url de publicación del servicio/ WebServicesListadosFE.svc

    # Servicio para obtener el Informe de cierre parcial de operaciones con autenticación en los cabezales SOAP:
    # Url de publicación del servicio/ WebServicesReportesFE.svc

    # 7.1.1 Consulta de CFE rechazados por DGI
    # Esta operación permitirá consultar los CFE rechazados de una empresa en determinada fecha.
    # Operación a invocar: ComprobantesPorEmpresaDenegadosPorDgi
    # Parámetros:
    # • rut, indicando el RUT de la empresa que emitió los CFE.
    # • fechaComprobante, indicando la fecha en la que se rechazaron los comprobantes.
    # Respuesta:
    # Arreglo de Comprobantes, conteniendo todos los comprobantes rechazados para la empresa indicada en la fch inform.
    # La entidad Comprobante contiene los siguientes campos:
    # ▪ CodigoComercio, conteniendo el código de la sucursal que emitió el comprobante.
    # ▪ CodigoTerminal, conteniendo el código del punto de emisión que emitió el comprobante.
    # ▪ Numero, conteniendo el número del comprobante.
    # ▪ Serie, conteniendo la serie del comprobante.
    # ▪ TipoCfe, conteniendo el tipo del CFE según su número indicado en DGI
    # ▪ Uuid, conteniendo el identificador externo asignado al CFE
