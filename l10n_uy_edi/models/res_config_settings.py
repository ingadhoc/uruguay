# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from datetime import datetime


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_uy_country_code = fields.Char(related='company_id.country_id.code', string='Country Code (UY)')

    # TODO This one should be interger but does not work because the interger is to long
    l10n_uy_ucfe_user = fields.Char(related='company_id.l10n_uy_ucfe_user', readonly=False)
    l10n_uy_ucfe_password = fields.Char(related='company_id.l10n_uy_ucfe_password', readonly=False)
    l10n_uy_ucfe_commerce_code = fields.Char(related='company_id.l10n_uy_ucfe_commerce_code', readonly=False)
    l10n_uy_ucfe_terminal_code = fields.Char(related='company_id.l10n_uy_ucfe_terminal_code', readonly=False)
    l10n_uy_ucfe_inbox_url = fields.Char(related='company_id.l10n_uy_ucfe_inbox_url', readonly=False)
    l10n_uy_ucfe_query_url = fields.Char(related='company_id.l10n_uy_ucfe_query_url', readonly=False)
    l10n_uy_ucfe_env = fields.Selection(related='company_id.l10n_uy_ucfe_env', readonly=False)

    l10n_uy_dgi_crt = fields.Binary(related='company_id.l10n_uy_dgi_crt', readonly=False)
    l10n_uy_dgi_crt_fname = fields.Char(related='company_id.l10n_uy_dgi_crt_fname')
    l10n_uy_dgi_house_code = fields.Integer(related='company_id.l10n_uy_dgi_house_code', readonly=False)

    def l10n_uy_connection_test(self):
        """ Make a ECO test to UCFE """
        self.ensure_one()
        now = datetime.utcnow()
        response = self.company_id._l10n_uy_ucfe_inbox_operation('820', {
            'FechaReq': now.date().strftime('%Y%m%d'),
            'HoraReq': now.strftime('%H%M%S')})
        if response.ErrorCode == 0 and response.ErrorMessage is None and response.Resp.TipoMensaje == 821:
            raise UserError(_('Everything is ok!'))

        raise UserError(_('Connection problems, this is what we get %s') % response)

    @api.onchange('l10n_uy_ucfe_env')
    def uy_onchange_ufce_env(self):
        """ Update UCFE param with what we have when Environment change."""

        if self.l10n_uy_ucfe_env == 'production':
            config = self.company_id.l10n_uy_ucfe_prod_env
        elif self.l10n_uy_ucfe_env == 'testing':
            config = self.company_id.l10n_uy_ucfe_test_env
        else:
            config = False

        config = safe_eval(config or "{}")
        uruware_fields = [
            'l10n_uy_ucfe_user', 'l10n_uy_ucfe_password', 'l10n_uy_ucfe_commerce_code',
            'l10n_uy_ucfe_terminal_code', 'l10n_uy_ucfe_inbox_url', 'l10n_uy_ucfe_query_url']
        for ufce_field in uruware_fields:
            self[ufce_field] = config.get(ufce_field, '')

    def set_values(self):
        super().set_values()
        self.uy_update_saved_param_data()

    def uy_update_saved_param_data(self):
        """ If any of the ucfe params change then update the env_data values of the current selected environment"""
        # Create dictionary with the data
        import pprint
        env_data = {
            'l10n_uy_ucfe_user': self.l10n_uy_ucfe_user or '',
            'l10n_uy_ucfe_password': self.l10n_uy_ucfe_password or '',
            'l10n_uy_ucfe_commerce_code': self.l10n_uy_ucfe_commerce_code or '',
            'l10n_uy_ucfe_terminal_code': self.l10n_uy_ucfe_terminal_code or '',
            'l10n_uy_ucfe_inbox_url': self.l10n_uy_ucfe_inbox_url or '',
            'l10n_uy_ucfe_query_url': self.l10n_uy_ucfe_query_url or '',
        }

        if self.l10n_uy_ucfe_env == 'production':
            env_data.update({'l10n_uy_ucfe_prod_env': pprint.pformat(env_data)})
        elif self.l10n_uy_ucfe_env == 'testing':
            env_data.update({'l10n_uy_ucfe_test_env': pprint.pformat(env_data)})

        self.company_id.write(env_data)
