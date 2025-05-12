from odoo.addons.l10n_uy_edi.tests.test_mock import TestMock

from . import common


class TestMockL10nUyUx(TestMock, common.TestUyEdiL10nUyUx):
    def test_150_cron_usd_vendor_bill(self):
        """Simulate the run of 'UY: Create vendor bills (sync from Uruware)' cron and create an invoice with USD currency.
        If multiple partners exist with the same RUC, select any of them."""
        partner_with_usd_account_payable = self._create_uy_partner(
            partner_name="Administración Nacional de Redes", vat="212466600018"
        )
        partner_without_usd_account_payable = self._create_uy_partner(
            partner_name="Administración Nacional de Redes", vat="212466600018"
        )
        account_with_usd_currency = self._search_account_liability_payable(code="211010")
        account_with_usd_currency.currency_id = self.env.ref("base.USD").id
        # Set the USD account as the partner's account payable
        partner_with_usd_account_payable.property_account_payable_id = account_with_usd_currency

        self._mock_cron_l10n_uy_edi_get_vendor_bills("test_150_cron_usd_vendor_bill")
        new_move_created = self.env["account.move"].search([], limit=1)
        self.assertEqual(
            new_move_created.partner_id.id,
            partner_without_usd_account_payable.id or partner_with_usd_account_payable.id,
        )
        self.assertEqual(new_move_created.currency_id.id, self.env.ref("base.USD").id)

    def test_160_cron_uyu_vendor_bill(self):
        """Simulate the run of 'UY: Create vendor bills (sync from Uruware)' cron and create an invoice with UYU currency.
        If multiple partners exist with the same RUC, select the partner with a UYU account payable's account currency."""
        partner_with_usd_account_payable = self._create_uy_partner(
            partner_name="Administración Nacional de Limpieza", vat="219999830019"
        )
        partner_without_usd_account_payable = self._create_uy_partner(
            partner_name="Administración Nacional de Limpieza", vat="219999830019"
        )
        account_with_usd_currency = self._search_account_liability_payable(code="211010")
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
        partner_with_usd_account_payable = self._create_uy_partner(
            partner_name="Administración Nacional de Comunicaciones", vat="211319220018"
        )
        account_with_usd_currency = self._search_account_liability_payable(code="211010")
        account_with_usd_currency.currency_id = self.env.ref("base.USD").id
        partner_with_usd_account_payable.property_account_payable_id = account_with_usd_currency

        self._mock_cron_l10n_uy_edi_get_vendor_bills("test_170_cron_uyu_vendor_bill_and_usd_partner")
        new_move_created = self.env["account.move"].search([], limit=1)
        self.assertEqual(new_move_created.partner_id.id, partner_with_usd_account_payable.id)
        self.assertEqual(new_move_created.currency_id.id, self.company_uy.currency_id.id)
        self.assertEqual(new_move_created.invoice_line_ids, self.env["account.move.line"])
