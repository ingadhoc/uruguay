##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging
from unittest.mock import patch

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged

_logger = logging.getLogger(__name__)


@tagged("post_install_l10n", "post_install", "-at_install")
class TestL10nUyCurrencyUpdate(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("uy")
    def setUpClass(cls):
        super().setUpClass()
        cls.UYU = cls.env.ref("base.UYU")
        cls.UYI = cls.env.ref("base.UYI")
        cls.ARS = cls.env.ref("base.ARS")
        cls.USD = cls.env.ref("base.USD")
        cls.EUR = cls.env.ref("base.EUR")
        (cls.ARS + cls.USD + cls.EUR).active = True
        cls.utils_path = "odoo.addons.currency_rate_live.models.res_config_settings.ResCompany"

    def test_company_config(self):
        # UYU es la moneda principal, por lo que su tasa de cambio debe ser 1.0
        self.assertEqual(self.UYU.rate, 1.0)

        # UYU y UYI deben estar activas por ser compañia uruguaya
        self.assertTrue(self.UYU.active, 1.0)
        self.assertTrue(self.UYI.active, 1.0)

        # verificamos config de proveedor a banco central uruguayp se haga configurado automaticamnete todo bien
        self.assertTrue(self.env.company.currency_provider, "bcu")

    def test_bcu_rates(self):
        self.assertEqual(self.UYU.rate, 1.0)
        test_date = fields.Date.today()
        mocked_res = {
            "ARS": (28.57142857142857, test_date),
            "EUR": (0.021456809662928324, test_date),
            "USD": (0.023986567522187575, test_date),
            "UYI": (0.16387263818560216, test_date),
            "UYU": (1.0, test_date),
        }

        with patch(f"{self.utils_path}._parse_bcu_data", return_value=mocked_res):
            # Use l10n_ar_force_create_rate context to avoid filtering by l10n_ar_currency_update
            self.env.company.with_context(l10n_ar_force_create_rate=True).update_currency_rates()

        # Hacer flush y invalidar cache para refrescar los campos computados
        self.env.flush_all()
        self.env.invalidate_all()

        # las cotizaciones se aplicaron correctamente
        self.assertEqual(self.UYU.rate, 1.0)
        self.assertAlmostEqual(self.USD.rate, 0.023986567522187575, places=16)
        self.assertAlmostEqual(self.EUR.rate, 0.021456809662928324, places=16)
        self.assertAlmostEqual(self.ARS.rate, 28.57142857142857, places=16)
        self.assertAlmostEqual(self.UYI.rate, 0.16387263818560216, places=16)
