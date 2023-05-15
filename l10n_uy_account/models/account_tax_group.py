from odoo import api, fields, models


class AccountTaxGroup(models.Model):

    _inherit = 'account.tax.group'

    l10n_uy_form = fields.Char("(UY) Form")
    l10n_uy_code = fields.Char("(UY) Code")
    l10n_uy_imprubro = fields.Char("(UY) Rubro")
    l10n_uy_description = fields.Char("(UY) Description")
    l10n_uy_retention = fields.Boolean("(UY) Is Retention")
