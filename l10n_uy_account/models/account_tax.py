from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_uy_dgi_code = fields.Char('DGI Code')
