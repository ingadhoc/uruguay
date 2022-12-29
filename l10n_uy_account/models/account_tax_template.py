from odoo import fields, models


class AccountTaxTemplate(models.Model):

    _inherit = 'account.tax.template'

    l10n_uy_dgi_code = fields.Char('DGI Code')

    def _get_tax_vals(self, company, tax_template_to_tax):
        vals = super()._get_tax_vals(company, tax_template_to_tax)
        if self.l10n_uy_dgi_code:
            vals['l10n_uy_dgi_code'] = self.l10n_uy_dgi_code
        return vals
