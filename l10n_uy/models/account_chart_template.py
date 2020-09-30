# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api


class AccountChartTemplate(models.Model):

    _inherit = 'account.chart.template'

    @api.model
    def _prepare_all_journals(self, acc_template_ref, company, journals_dict=None):
        """ By default sale and purchase journals are created as pre printed """
        journal_data = super()._prepare_all_journals(acc_template_ref, company, journals_dict)
        if company.country_id.code == 'UY':
            for values in journal_data:
                if values['type'] in ['sale', 'purchase']:
                    values['l10n_uy_type'] = 'preprinted'
        return journal_data

    def _load(self, sale_tax_rate, purchase_tax_rate, company):
        """ Set companies AFIP Responsibility and Country if AR CoA is installed, also set tax calculation rounding
        method required in order to properly validate match AFIP invoices.

        Also, raise a warning if the user is trying to install a CoA that does not match with the defined AFIP
        Responsibility defined in the company
        """
        self.ensure_one()
        res = super()._load(sale_tax_rate, purchase_tax_rate, company)

        if self == self.env.ref('l10n_uy.l10n_uy_chart_template'):
            company.write({
                'country_id': self.env.ref('base.uy').id,
            })
            # set RUT as identification type (which is the uruguayan vat) in the created company partner instead of
            # the default VAT type.
            company.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_uy.it_rut')
        return res
