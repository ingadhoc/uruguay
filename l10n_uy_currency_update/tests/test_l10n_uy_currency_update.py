##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestL10nUyCurrencyUpdate(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref="uy"):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.UYU = cls.env.ref('base.UYU')
        cls.UYI = cls.env.ref('base.UYI')
        cls.ARS = cls.env.ref('base.ARS')
        cls.USD = cls.env.ref('base.USD')
        cls.EUR = cls.env.ref('base.EUR')

        (cls.UYU + cls.UYI + cls.ARS + cls.USD + cls.EUR).active = True

        cls.utils_path = "odoo.addons.currency_rate_live.models.res_config_settings.ResCompany"

    def test_bcu_rates(self):
        """ When the base currency is UYU """
        self.assertEqual(self.USD.rate, 1.0)
        self.assertEqual(self.EUR.rate, 1.0)
        self.assertEqual(self.ARS.rate, 1.0)
        self.assertEqual(self.UYI.rate, 1.0)

        test_date = datetime.date(2024, 9, 26)
        mocked_res = {
            'ARS': (28.57142857142857, test_date),
            'EUR': (0.021456809662928324, test_date),
            'USD': (0.023986567522187575, test_date),
            'UYI': (0.16387263818560216, test_date),
            'UYU': (1.0, test_date),
        }

        with patch(f"{self.utils_path}._parse_bcu_data", return_value=mocked_res):
            self.env.company.update_currency_rates()

        self.assertEqual(self.UYU.rate, 1.0)
        self.assertAlmostEqual(self.USD.rate, 0.023986567522187575, places=16)
        self.assertAlmostEqual(self.EUR.rate, 0.021456809662928324, places=16)
        self.assertAlmostEqual(self.ARS.rate, 28.57142857142857, places=16)
        self.assertAlmostEqual(self.UYI.rate, 0.16387263818560216, places=16)
