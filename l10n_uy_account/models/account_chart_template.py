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

    def _load(self, company):
        """ Set companies country by default after install the chrar of account, also set the rut as the company
        identification type because this one is the uruguayan vat """
        self.ensure_one()
        res = super()._load(company)

        if self == self.env.ref('l10n_uy_account.l10n_uy_chart_template'):
            company.write({
                'country_id': self.env.ref('base.uy').id,
            })
            # set RUT as identification type (which is the uruguayan vat) in the created company partner instead of
            # the default VAT type.
            company.partner_id.l10n_latam_identification_type_id = self.env.ref('l10n_uy_account.it_rut')
        return res
