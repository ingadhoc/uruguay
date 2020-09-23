# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, _
from odoo.exceptions import UserError
from datetime import datetime


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_uy_country_code = fields.Char(related='company_id.country_id.code', string='Country Code')

    # TODO This one should be interger but does not work because the interger is to long
    l10n_uy_ucfe_user = fields.Char(related='company_id.l10n_uy_ucfe_user', readonly=False)
    l10n_uy_ucfe_password = fields.Char(related='company_id.l10n_uy_ucfe_password', readonly=False)
    l10n_uy_ucfe_commerce_code = fields.Char(related='company_id.l10n_uy_ucfe_commerce_code', readonly=False)
    l10n_uy_ucfe_terminal_code = fields.Char(related='company_id.l10n_uy_ucfe_terminal_code', readonly=False)
    l10n_uy_ucfe_inbox_url = fields.Char(related='company_id.l10n_uy_ucfe_inbox_url', readonly=False)
    l10n_uy_ucfe_query_url = fields.Char(related='company_id.l10n_uy_ucfe_query_url', readonly=False)

    l10n_uy_dgi_crt = fields.Binary(related='company_id.l10n_uy_dgi_crt', readonly=False)
    l10n_uy_dgi_crt_fname = fields.Char(related='company_id.l10n_uy_dgi_crt_fname')
    l10n_uy_dgi_house_code = fields.Integer(related='company_id.l10n_uy_dgi_house_code', readonly=False)

    def l10n_uy_connection_test(self):
        """ Make a ECO test to UCFE """
        self.ensure_one()
        client, _auth = self.company_id._get_client()
        now = datetime.utcnow()

        # TODO review if odoo already save utc, if true then use fields.Datetime.now() directly
        data = {
            'Req': {
                'TipoMensaje': '820',
                'CodComercio': self.l10n_uy_ucfe_commerce_code,
                'CodTerminal': self.l10n_uy_ucfe_terminal_code,
                'FechaReq': now.date().strftime('%Y%m%d'),
                'HoraReq': now.strftime('%H%M%S')},
            'RequestDate': now.replace(microsecond=0).isoformat(),
            'Tout': '30000',
            'CodComercio': self.l10n_uy_ucfe_commerce_code,
            'CodTerminal': self.l10n_uy_ucfe_terminal_code
        }

        response = client.service.Invoke(data)
        if response.ErrorCode == 0 and response.ErrorMessage is None and response.Resp.TipoMensaje == 821:
            raise UserError(_('Everything is ok!'))

        raise UserError(_('Connection problems, this is what we get %s') % response)
