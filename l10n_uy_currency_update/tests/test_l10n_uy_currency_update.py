##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import datetime
import logging
from unittest.mock import patch

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestL10nUyCurrencyUpdate(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_chart_template("uy")
    def setUpClass(cls):
        logging.getLogger("odoo.addons.account.models.chart_template").setLevel(logging.ERROR)
        super().setUpClass()
        cls.UYU = cls.env.ref("base.UYU")
        cls.UYI = cls.env.ref("base.UYI")
        cls.ARS = cls.env.ref("base.ARS")
        cls.USD = cls.env.ref("base.USD")
        cls.EUR = cls.env.ref("base.EUR")

        (cls.UYU + cls.UYI + cls.ARS + cls.USD + cls.EUR).active = True

        cls.utils_path = "odoo.addons.currency_rate_live.models.res_config_settings.ResCompany"

    def test_bcu_rates(self):
        """When the base currency is UYU"""
        test_date = datetime.date(2024, 9, 26)
        mocked_res = {
            "ARS": (28.57142857142857, test_date),
            "EUR": (0.021456809662928324, test_date),
            "USD": (0.023986567522187575, test_date),
            "UYI": (0.16387263818560216, test_date),
            "UYU": (1.0, test_date),
        }

        with patch(f"{self.utils_path}._parse_bcu_data", return_value=mocked_res):
            self.env.company.update_currency_rates()

        self.env.invalidate_all()

        self.assertEqual(self.UYU.rate, 1.0)
        self.assertAlmostEqual(self.USD.rate, 0.023986567522187575, places=16)
        self.assertAlmostEqual(self.EUR.rate, 0.021456809662928324, places=16)
        self.assertAlmostEqual(self.ARS.rate, 28.57142857142857, places=16)
        self.assertAlmostEqual(self.UYI.rate, 0.16387263818560216, places=16)
