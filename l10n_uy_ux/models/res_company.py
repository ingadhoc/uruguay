# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = "res.company"

    l10n_uy_edi_ucfe_prod_env = fields.Text("Uruware Production Data", groups="base.group_system", default="{}")
    l10n_uy_edi_ucfe_test_env = fields.Text("Uruware Testing Data", groups="base.group_system", default="{}")

    l10n_uy_report_params = fields.Char()

    # DGI informative fields.
    l10n_uy_dgi_crt_id = fields.Many2one(
        "certificate.certificate", "DGI Certificate", groups="base.group_system",
        help="This certificate lets us connect to DGI to validate electronic invoice."
        " Please upload here the DGI certificate in PEM format and its password.")
