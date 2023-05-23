from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_uy_dgi_code = fields.Many2one('l10n.uy.tax.type', "DGI Tax Type")
