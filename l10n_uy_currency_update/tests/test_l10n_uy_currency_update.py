##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.tests import common
from odoo import fields
from unittest.mock import patch


class TestL10nUyCurrencyUpdate(common.TransactionCase):

    # TODO when running this test please update this values to the day rate.
    # can use only rates of the last 30 days

    def setUp(self):

        self.frozen_date = fields.Date.from_string('2022-03-17')
        self.UYU_USD = 1.0 / 42.652
        self.UYU_EUR = 1.0 / 46.923598
        self.UYU_ARS = 1.0 / 0.389819
        self.UYU_UYI = 1.0 / 5.2768

        super().setUp()

        self.UYU = self.env.ref('base.UYU')
        self.UYI = self.env.ref('l10n_uy_account.UYI')
        self.ARS = self.env.ref('base.ARS')
        self.USD = self.env.ref('base.USD')
        self.EUR = self.env.ref('base.EUR')

    def test_bcu_rates(self):
        """ When the base currency is UYU """
        company = self.env.ref('l10n_uy_account.company_uy')
        company.currency_id = self.UYU
        self.env.company = company

        with patch.object(fields.Date, 'today', lambda *args, **kwargs: self.frozen_date), \
             patch.object(fields.Date, 'context_today', lambda *args, **kwargs: self.frozen_date), \
             patch.object(type(self.env['res.company']), 'get_bcu_last_date', lambda *args, **kwargs: fields.Date.subtract(self.frozen_date, days=1)):

            company.update_currency_rates()

            self.assertEqual(self.UYU.rate, 1.0)
            self.assertAlmostEqual(self.USD.rate, self.UYU_USD, places=3)
            self.assertAlmostEqual(self.EUR.rate, self.UYU_EUR, places=3)
            self.assertAlmostEqual(self.ARS.rate, self.UYU_ARS, places=3)
            self.assertAlmostEqual(self.UYI.rate, self.UYU_UYI, places=3)
