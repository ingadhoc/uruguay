# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
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
    l10n_uy_ucfe_env = fields.Selection(related='company_id.l10n_uy_ucfe_env', readonly=False)
    l10n_uy_ucfe_prod_env = fields.Text(related='company_id.l10n_uy_ucfe_prod_env', readonly=False)
    l10n_uy_ucfe_test_env = fields.Text(related='company_id.l10n_uy_ucfe_test_env', readonly=False)

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

    @api.onchange('l10n_uy_ucfe_env', 'l10n_uy_ucfe_prod_env', 'l10n_uy_ucfe_test_env')
    def onchange_ufce_env(self):
        config = self.l10n_uy_ucfe_prod_env if self.l10n_uy_ucfe_env == 'production' \
            else self.l10n_uy_ucfe_test_env
        config = safe_eval(config or "{}")

        # If not environment selected then clean the ucfe parameters
        if not self.l10n_uy_ucfe_env:
            self.clean_ucfe_config_values()

        # If environment set but not defined keys request to configure the ucfe data
        # clean up the config values
        if not config:
            self.clean_ucfe_config_values()
            return

        # field the ucfe fields with the date of the selected environment
        for ufce_field, value in config.items():
            self[ufce_field] = value

    def clean_ucfe_config_values(self):
        ucfe_fields = ['l10n_uy_ucfe_user', 'l10n_uy_ucfe_password', 'l10n_uy_ucfe_commerce_code', 'l10n_uy_ucfe_terminal_code', 'l10n_uy_ucfe_inbox_url', 'l10n_uy_ucfe_query_url']
        for item in ucfe_fields:
            self[item] = False
