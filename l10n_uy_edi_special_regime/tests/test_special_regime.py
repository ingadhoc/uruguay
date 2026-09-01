from odoo import Command
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("-at_install", "post_install", "post_install_l10n")
class TestUyEdiSpecialRegime(TestUyEdi):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_uy.l10n_uy_edi_ucfe_env = "demo"
        cls.company_uy.l10n_uy_edi_taxpayer_regime = "iva_minimo"
        cls.mocked_cfes_path = "l10n_uy_edi_special_regime/tests/expected_cfes/"
        cls.service_exempt = cls.env["product.product"].create(
            {
                "name": "Service Exempt (Literal E)",
                "list_price": 100.0,
                "standard_price": 100.0,
                "type": "service",
                "default_code": "EXEMPT",
                "taxes_id": [(6, 0, cls.tax_0.ids)],
            }
        )

    def _create_exempt_move(self, **kwargs):
        return self._create_move(
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.service_exempt.id,
                        "quantity": 1.0,
                        "price_unit": 100.0,
                    }
                )
            ],
            **kwargs,
        )

    def test_10_literal_e_e_ticket(self):
        """e-Ticket under special regime must report MntBruto = 3 and IndFact = 16"""
        invoice = self._create_exempt_move()
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "101", "Not e-Ticket")
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-TK", "10_literal_e_e_ticket")

    def test_20_literal_e_e_invoice(self):
        """e-Invoice under special regime must report MntBruto = 3 and IndFact = 16"""
        invoice = self._create_exempt_move(partner_id=self.partner_local.id)
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "111", "Not e-Invoice")
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-FC", "20_literal_e_e_invoice")

    def test_30_literal_e_e_ticket_credit_note(self):
        invoice = self._create_exempt_move()
        invoice.action_post()
        self._send_and_print(invoice)

        refund = self._create_credit_note(invoice)
        refund.action_post()
        self.assertEqual(refund.l10n_latam_document_type_id.code, "102", "Not e-Ticket Credit Note")
        self._send_and_print(refund)
        self._check_cfe(refund, "e-NCTK", "30_literal_e_e_ticket_credit_note")

    def test_40_literal_e_e_ticket_debit_note(self):
        invoice = self._create_exempt_move()
        invoice.action_post()
        self._send_and_print(invoice)

        debit_note = self._create_debit_note(invoice)
        debit_note.action_post()
        self.assertEqual(debit_note.l10n_latam_document_type_id.code, "103", "Not e-Ticket Debit Note")
        self._send_and_print(debit_note)
        self._check_cfe(debit_note, "e-NDTK", "40_literal_e_e_ticket_debit_note")

    def test_50_literal_e_e_invoice_credit_note(self):
        invoice = self._create_exempt_move(partner_id=self.partner_local.id)
        invoice.action_post()
        self._send_and_print(invoice)

        refund = self._create_credit_note(invoice)
        refund.action_post()
        self.assertEqual(refund.l10n_latam_document_type_id.code, "112", "Not e-Invoice Credit Note")
        self._send_and_print(refund)
        self._check_cfe(refund, "e-NC", "50_literal_e_e_invoice_credit_note")

    def test_60_literal_e_e_invoice_debit_note(self):
        invoice = self._create_exempt_move(partner_id=self.partner_local.id)
        invoice.action_post()
        self._send_and_print(invoice)

        debit_note = self._create_debit_note(invoice)
        debit_note.action_post()
        self.assertEqual(debit_note.l10n_latam_document_type_id.code, "113", "Not e-Invoice Debit Note")
        self._send_and_print(debit_note)
        self._check_cfe(debit_note, "e-ND", "60_literal_e_e_invoice_debit_note")

    def test_70_no_regression_general_regime(self):
        """With the default (general) regime the generated CFE must be identical to the standard one:
        this test justifies that the module is inert for every other company."""
        self.company_uy.l10n_uy_edi_taxpayer_regime = "general"
        self.mocked_cfes_path = "l10n_uy_edi/tests/expected_cfes/"
        invoice = self._create_move()
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-TK", "20_e_ticket")

    def test_90_literal_e_free_delivery(self):
        """Free delivery keeps its conceptual indicator (IndFact = 5) under the special regime:
        per Uruware, 16 only replaces the VAT rate indicators (1/2/3/4)."""
        invoice = self._create_move(
            partner_id=self.partner_local.id,
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.service_exempt.id,
                        "price_unit": 100.0,
                        "discount": 100.0,
                    }
                )
            ],
        )
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "111", "Not e-Invoice")
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-FC", "90_literal_e_free_delivery")

    def test_100_literal_e_global_discount(self):
        """Global discount lines follow the detail line indicators (per Uruware), so an exempt
        global discount reports IndFactDR = 16 under the special regime."""
        invoice = self._create_move(
            partner_id=self.partner_local.id,
            invoice_line_ids=[
                Command.create({"product_id": self.service_exempt.id, "price_unit": 100.0}),
                Command.create(
                    {
                        "name": "Global Discount",
                        "price_unit": -20.0,
                        "tax_ids": [(6, 0, self.tax_0.ids)],
                    }
                ),
            ],
        )
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "111", "Not e-Invoice")
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-FC", "100_literal_e_global_discount")

    def test_110_literal_e_expo_invoice(self):
        """Export CFEs keep the standard behavior under the special regime (IndFact = 10, no
        MntBruto = 3): the generated XML must be identical to the l10n_uy_edi standard one."""
        self.mocked_cfes_path = "l10n_uy_edi/tests/expected_cfes/"
        invoice = self._create_move(
            l10n_latam_document_type_id=self.env.ref("l10n_uy.dc_e_inv_exp").id,
            partner_id=self.foreign_partner.id,
            invoice_incoterm_id=self.env.ref("account.incoterm_FOB").id,
            l10n_uy_edi_cfe_sale_mode="1",
            l10n_uy_edi_cfe_transport_route="1",
            invoice_line_ids=[Command.create({"product_id": self.product_vat_22.id, "price_unit": 100.0})],
        )
        self.assertEqual(invoice.l10n_latam_document_type_id.code, "121", "Not Expo e-invoice")
        invoice.action_post()
        self._send_and_print(invoice)
        self._check_cfe(invoice, "e-FCE", "40_e_expo_invoice")

    def test_80_check_move_blocks_taxed_lines(self):
        """A special regime company must not be able to send a CFE with 10% / 22% VAT lines:
        each CFE rejected by DGI burns a CAE number, so we block before sending."""
        invoice = self._create_move()  # default line uses VAT 22
        errors = invoice._l10n_uy_edi_check_move()
        self.assertTrue(
            any("special DGI taxpayer regime" in error for error in errors),
            "Taxed lines on a special regime company should be rejected before sending",
        )
        with self.assertRaises(UserError, msg="Posting a CFE with taxed lines should be blocked"):
            invoice.action_post()

        exempt_invoice = self._create_exempt_move()
        errors = exempt_invoice._l10n_uy_edi_check_move()
        self.assertFalse(
            any("special DGI taxpayer regime" in error for error in errors),
            "Exempt lines should not raise the special regime error",
        )
