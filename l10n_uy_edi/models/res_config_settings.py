# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_ar_country_code = fields.Char(related='company_id.country_id.code', string='Country Code')

    l10n_uy_uruware_user = fields.Interger(related='company_id.l10n_uy_uruware_user', readonly=False)
    l10n_uy_uruware_password = fields.Char(related='company_id.l10n_uy_uruware_password', readonly=False)
    l10n_uy_uruware_commerce_code = fields.Char(related='company_id.l10n_uy_uruware_commerce_code', readonly=False)
    l10n_uy_uruware_terminal_code = fields.Char(related='company_id.l10n_uy_uruware_terminal_code', readonly=False)
    l10n_uy_uruware_inbox_url = fields.Interger(related='company_id.l10n_uy_uruware_inbox_url', readonly=False)
    l10n_uy_uruware_query_url = fields.Interger(related='company_id.l10n_uy_uruware_query_url', readonly=False)

    def l10n_ar_connection_test(self):
        """ Prueba de eco UCFE """
        self.ensure_one()
        client, _auth = self.company_id._get_client()
        data = {'Req': {'TipoMensaje': '820', 'CodComercio': self.l10n_uy_uruware_commerce_code,
                        'CodTerminal': self.l10n_uy_uruware_terminal_code,
                        'FechaReq': fields.Date.today().strftime('%Y%m%d'),  # '20200428'
                        'HoraReq': '120000'},           # TODO find format and add it,
                'RequestDate': '2020-04-28T12:00:00',   # TODO find format and applied,
                'Tout': '30000',                        # TODO found what it means this
                'CodComercio': self.l10n_uy_uruware_commerce_code,
                'CodTerminal': self.l10n_uy_uruware_terminal_code}

        response = client.service.Invoke(data)
        # TODO ensure that we do not have error and that we receive a 'TipoMensaje': '821', result
        # Codigo de respuesta CodRta
        # codigo de CodTerminal CodTerminal
        raise UserError(_('Everything is ok %s') % response)

# TODO interpretar CodRta
# 00 Petición aceptada y procesada.
# 01 Petición denegada.
# 03 Comercio inválido.
# 05 CFE rechazado por DGI.
# 06 CFE observado por DGI.
# 11 CFE aceptado por UCFE, en espera de respuesta de DGI.
# 12 Requerimiento inválido.
# 30 Error en formato.
# 31 Error en formato de CFE.
# 89 Terminal inválida.
# 96 Error en sistema.
# 99 Sesión no iniciada.
# ?  Cualquier otro código no especificado debe entenderse como requerimiento denegado.
