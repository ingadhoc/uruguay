##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

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
        cls.AED = cls.env.ref("base.AED")
        (cls.ARS + cls.USD + cls.EUR + cls.AED).active = True
        cls.utils_path = "odoo.addons.currency_rate_live.models.res_config_settings.ResCompany"
        cls.module_path = "odoo.addons.l10n_uy_currency_update.models.res_currency"

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

    def test_have_bcu_code(self):
        """The BCU buttons depend on whether the currency is in the BCU mapping."""
        for currency, expected in ((self.USD, True), (self.UYU, False), (self.AED, False)):
            with self.subTest(currency=currency.name):
                self.assertEqual(currency.l10n_uy_have_bcu_code, expected)

    def test_get_bcu_rate(self):
        """The button shows the last closing date and the rate in UYU per unit of the currency."""
        closing_date = fields.Date.from_string("2026-01-09")
        rate_date = fields.Date.from_string("2026-01-10")
        client = MagicMock()
        client.service.Execute.return_value = closing_date
        mocked_rates = {"USD": (0.025, rate_date), "UYU": (1.0, rate_date)}
        with (
            patch(f"{self.module_path}.Client", return_value=client),
            patch(f"{self.utils_path}._parse_bcu_data", return_value=mocked_rates) as parse,
            self.assertRaises(UserError) as error,
        ):
            self.USD.action_l10n_uy_get_bcu_rate()
        parse.assert_called_once_with(self.USD)
        self.assertEqual(str(error.exception), "Last Closing Date: %s\nRate: %s" % (closing_date, 40.0))

    def test_get_available_currencies(self):
        """The button lists the BCU currencies, split into configured and not configured in Odoo."""
        with self.subTest("lists configured and not configured currencies separately"):
            client = MagicMock()
            client.service.Execute.return_value = [
                SimpleNamespace(Codigo=2225, Nombre="DLS. USA BILLETE"),
                SimpleNamespace(Codigo=9999, Nombre="MONEDA DE PRUEBA"),
            ]
            with (
                patch(f"{self.module_path}.Client", return_value=client),
                self.assertRaises(UserError) as error,
            ):
                self.UYU.action_get_available_currencies()
            configured, not_configured = str(error.exception).split("(Not configured)")
            self.assertIn("* 2225 - DLS. USA BILLETE (USD - ID %s)" % self.USD.id, configured)
            self.assertNotIn("9999", configured)
            self.assertIn("* 9999 - MONEDA DE PRUEBA", not_configured)
            self.assertNotIn("2225", not_configured)

        with self.subTest("turns a ValueError from the web service into a UserError"):
            with (
                mute_logger(self.module_path),
                patch(f"{self.module_path}.Client", side_effect=ValueError("connection refused")),
                self.assertRaises(UserError) as error,
            ):
                self.UYU.action_get_available_currencies()
            self.assertIn("connection refused", str(error.exception))
