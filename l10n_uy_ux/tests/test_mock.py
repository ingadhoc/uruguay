from odoo.l10n_uy_edi.tests.test_mock import TestMock

from . import common


class TestMockL10nUyUx(common.TestMock):
    def test_150_cron_usd_vendor_bill(self):
        """Simulate the run of 'UY: Create vendor bills (sync from Uruware)' cron and create an invoice with USD currency. If multiple partners exist with the same RUC, select the partner with a USD account payable's account currency."""
        _partner_without_usd_account_payable = self.env["res.partner"].create(
            {
                "name": "Administración Nacional de Redes",
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": "212466600018",
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )
        partner_with_usd_account_payable = self.env["res.partner"].create(
            {
                "name": "Administración Nacional de Redes",
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": "212466600018",
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )
        account_with_usd_currency = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company_uy.id),
                ("account_type", "=", "liability_payable"),
                ("code", "=", "211010"),
            ],
            limit=1,
        )
        account_with_usd_currency.currency_id = self.env.ref("base.USD").id
        partner_with_usd_account_payable.property_account_payable_id = account_with_usd_currency

        self._mock_cron_l10n_uy_edi_get_vendor_bills("test_150_cron_usd_vendor_bill")
        new_move_created = self.env["account.move"].search([], limit=1)
        self.assertEqual(new_move_created.partner_id.id, partner_with_usd_account_payable.id)
        self.assertEqual(new_move_created.currency_id.id, self.env.ref("base.USD").id)

    def test_160_cron_uyu_vendor_bill(self):
        """Simulate the run of 'UY: Create vendor bills (sync from Uruware)' cron and create an invoice with UYU currency.
        If multiple partners exist with the same RUC, select the partner with a UYU account payable's account currency."""
        partner_without_usd_account_payable = self.env["res.partner"].create(
            {
                "name": "Administración Nacional de Limpieza",
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": "219999830019",
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )
        partner_with_usd_account_payable = self.env["res.partner"].create(
            {
                "name": "Administración Nacional de Limpieza",
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": "219999830019",
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )
        account_with_usd_currency = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company_uy.id),
                ("account_type", "=", "liability_payable"),
                ("code", "=", "211010"),
            ],
            limit=1,
        )
        account_with_usd_currency.currency_id = self.env.ref("base.USD").id
        partner_with_usd_account_payable.property_account_payable_id = account_with_usd_currency

        self._mock_cron_l10n_uy_edi_get_vendor_bills("test_160_cron_uyu_vendor_bill")
        new_move_created = self.env["account.move"].search([], limit=1)
        self.assertEqual(new_move_created.partner_id.id, partner_without_usd_account_payable.id)
        self.assertEqual(new_move_created.currency_id.id, self.company_uy.currency_id.id)

    def test_170_cron_uyu_vendor_bill_and_usd_partner(self):
        """Simulate the run of 'UY: Create vendor bills (sync from Uruware)' cron and create an invoice with UYU currency.
        There exists only one partner with the same RUC but with a USD account payable's account currency. So the invoice
        is created without invoices lines."""
        partner_with_usd_account_payable = self.env["res.partner"].create(
            {
                "name": "Administración Nacional de Comunicaciones",
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": "211319220018",
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )
        account_with_usd_currency = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company_uy.id),
                ("account_type", "=", "liability_payable"),
                ("code", "=", "211010"),
            ],
            limit=1,
        )
        account_with_usd_currency.currency_id = self.env.ref("base.USD").id
        partner_with_usd_account_payable.property_account_payable_id = account_with_usd_currency

        self._mock_cron_l10n_uy_edi_get_vendor_bills("test_170_cron_uyu_vendor_bill_and_usd_partner")
        new_move_created = self.env["account.move"].search([], limit=1)
        self.assertEqual(new_move_created.partner_id.id, partner_with_usd_account_payable.id)
        self.assertEqual(new_move_created.currency_id.id, self.company_uy.currency_id.id)
        self.assertEqual(new_move_created.invoice_line_ids, self.env["account.move.line"])
