# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class ResCompany(models.Model):

    _inherit = "res.company"

    l10n_uy_ucfe_prod_env = fields.Text('Uruware Production Data', groups="base.group_system", default="{}")
    l10n_uy_ucfe_test_env = fields.Text('Uruware Testing Data', groups="base.group_system", default="{}")

    l10n_uy_report_params = fields.Char()

    # DGI informative files
    l10n_uy_dgi_crt = fields.Binary(
        'DGI Certificate', groups="base.group_system", help="This certificate lets us"
        " connect to DGI to validate electronic invoice. Please upload here the DGI certificate in PEM format.")
    l10n_uy_dgi_crt_fname = fields.Char('DGI Certificate name')
    l10n_uy_dgi_crt_pass = fields.Char('Private Password')

    def action_update_from_config(self):
        self.ensure_one()
        config = False
        if self.l10n_uy_ucfe_env == 'production':
            config = self.l10n_uy_ucfe_prod_env
        elif self.l10n_uy_ucfe_env == 'testing':
            config = self.l10n_uy_ucfe_test_env

        config = safe_eval(config or "{}")
        self.write(config)

    def _l10n_uy_edi_ucfe_inbox_operation(self, msg_type, extra_req={}, return_transport=True):
        """ sobre escribimos super solo para definir que siempre devuelva el transport asi almacenamos el xml request/response """
        return super()._l10n_uy_edi_ucfe_inbox_operation(msg_type, extra_req=extra_req, return_transport=return_transport)

    def _l10n_uy_edi_get_client(self, url, return_transport=True):
        return super()._l10n_uy_edi_get_client(url, return_transport=return_transport)
