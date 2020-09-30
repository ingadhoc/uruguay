from odoo import api, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _l10n_uy_get_taxes(self):
        """ return the related taxes recordset for basica, minima y exento """
        taxes = self.search([])
        current_company = self.env.user.company_id
        tax_vat_22 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_22") and x.company_id == current_company)
        tax_vat_10 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_10") and x.company_id == current_company)
        tax_vat_exempt = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_exempt") and x.company_id == current_company)
        return tax_vat_22, tax_vat_10, tax_vat_exempt
