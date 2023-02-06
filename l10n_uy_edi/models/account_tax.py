from odoo import api, models, _
from odoo.exceptions import UserError


class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _l10n_uy_get_taxes(self, company):
        """ return the related sales vat taxes recordset for basica, minima y exento """
        taxes = self.search([('company_id', '=', company.id)])
        tax_vat_22 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy_account.tax_group_vat_22"))
        tax_vat_10 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy_account.tax_group_vat_10"))
        tax_vat_exempt = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy_account.tax_group_vat_exempt"))

        if not tax_vat_22 or not tax_vat_10 or not tax_vat_exempt:
            raise UserError(_('No se pudo encontrar alguno de los siguientes impuestos para la compañía %s:') % company.name +
                            _('\n - IVA Ventas 22%\n - IVA Ventas 10%\n - IVA Ventas Exento'))

        return tax_vat_22[0], tax_vat_10[0], tax_vat_exempt[0]
