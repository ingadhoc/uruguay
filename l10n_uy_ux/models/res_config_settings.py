# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields
from odoo.tools.safe_eval import safe_eval


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_uy_dgi_crt = fields.Binary(related='company_id.l10n_uy_dgi_crt', readonly=False)
    l10n_uy_dgi_crt_fname = fields.Char(related='company_id.l10n_uy_dgi_crt_fname', readonly=False)
    l10n_uy_dgi_crt_pass = fields.Char(related='company_id.l10n_uy_dgi_crt_pass', readonly=False)
    l10n_uy_report_params = fields.Char(
        related='company_id.l10n_uy_report_params', readonly=False
    )

    l10n_uy_ucfe_get_vendor_bills = fields.Boolean(related='company_id.l10n_uy_ucfe_get_vendor_bills', readonly=False)

    @api.onchange('l10n_uy_edi_ucfe_env')
    def uy_onchange_ufce_env(self):
        """ Update UCFE param with what we have when Environment change."""

        if self.l10n_uy_edi_ucfe_env == 'production':
            config = self.company_id.l10n_uy_ucfe_prod_env
        elif self.l10n_uy_edi_ucfe_env == 'testing':
            config = self.company_id.l10n_uy_ucfe_test_env
        else:
            config = False

        config = safe_eval(config or "{}")
        uruware_fields = ['l10n_uy_ucfe_password', 'l10n_uy_ucfe_commerce_code',
            'l10n_uy_ucfe_terminal_code']
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
            'l10n_uy_ucfe_password': self.l10n_uy_ucfe_password or '',
            'l10n_uy_ucfe_commerce_code': self.l10n_uy_ucfe_commerce_code or '',
            'l10n_uy_ucfe_terminal_code': self.l10n_uy_ucfe_terminal_code or '',
        }

        if self.l10n_uy_edi_ucfe_env == 'production':
            env_data.update({'l10n_uy_ucfe_prod_env': pprint.pformat(env_data)})
        elif self.l10n_uy_edi_ucfe_env == 'testing':
            env_data.update({'l10n_uy_ucfe_test_env': pprint.pformat(env_data)})

        self.company_id.write(env_data)
