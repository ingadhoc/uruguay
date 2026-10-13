# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_uy_dgi_department_code = fields.Selection(related="company_id.l10n_uy_dgi_department_code", readonly=False)
    l10n_uy_dgi_locality_code = fields.Char(related="company_id.l10n_uy_dgi_locality_code", readonly=False)
