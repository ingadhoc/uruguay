from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'


    # TODO KZ estamos teniendo este error """KeyError: 'Field l10n_uy_code referenced in related field definition account.tax.l10n_uy_code does not exist.' - - - no se porque. lo comentamos por los momentos realmente no se si lo vamos a necesitar"""

    # l10n_uy_code = fields.Char(related="tax_group_id.l10n_uy_code")
