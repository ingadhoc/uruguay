from odoo import fields, models


class AccountTaxGroup(models.Model):

    _inherit = 'account.tax.group'

    l10n_uy_vat_code = fields.Selection(
        [('vat_22', 'VAT 22%'),
         ('vat_10', 'VAT 10%'),
         ('vat_exempt', 'Exempt')],
        string='VAT Code (UY)',
        help="Tehcnical field used to identify the VAT taxes to print on the VAT book report",
        index=True, readonly=True,
    )
