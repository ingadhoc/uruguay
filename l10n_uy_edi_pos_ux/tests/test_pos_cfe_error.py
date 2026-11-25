import base64
from unittest.mock import patch

from odoo.tests import tagged

from .common import TestPosCfeErrorCommon

GET_PDF = "odoo.addons.l10n_uy_edi.models.l10n_uy_edi_document.L10n_Uy_EdiDocument._get_pdf"


@tagged("-at_install", "post_install", "post_install_l10n")
class TestPosCfeError(TestPosCfeErrorCommon):
    def test_cfe_error_keeps_the_invoice_posted(self):
        """The sale goes on; the invoice stays posted with its temporary name, without PDF or proforma."""
        self._cfe_error_mode()
        order = self._sell(self._create_config())
        invoice = order.account_move
        self.assertEqual(order.state, "done")
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertEqual(invoice.name, f"* {invoice.id}")
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertFalse(self._pdf_attachments(invoice), "No PDF nor proforma without a validated CFE")
        self.assertTrue(invoice._l10n_uy_edi_pos_without_cfe())
        self.assertEqual(order.l10n_uy_edi_cfe_state, "error")

        result = invoice.l10n_uy_edi_pos_download_invoice()
        self.assertNotIn("action", result, "The POS must not print an invoice without CFE")
        self.assertTrue(result["error"])

    def test_pdf_asked_once_when_printed(self):
        """The sale does not ask Uruware for the PDF. The first print does, and the next ones use the same file."""
        order = self._sell(self._create_config())
        invoice = order.account_move
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertFalse(invoice.invoice_pdf_report_id, "No PDF in the sale, neither from Uruware nor from Odoo")
        self.assertFalse(self._pdf_attachments(invoice))

        # Printing a validated CFE asks Uruware, as with real credentials
        self.company_uy.write({"l10n_uy_edi_ucfe_env": "testing", "l10n_uy_edi_ucfe_password": "password_xxx"})
        pdf = {"file_content": base64.b64encode(b"%PDF-1.4 Uruware")}
        with patch(GET_PDF, autospec=True, return_value=pdf) as get_pdf:
            first = invoice.l10n_uy_edi_pos_download_invoice()
            second = invoice.l10n_uy_edi_pos_download_invoice()
        self.assertEqual(get_pdf.call_count, 1)
        self.assertEqual(first["action"]["type"], "ir.actions.act_url")
        self.assertEqual(second["action"], first["action"])
        self.assertTrue(invoice.invoice_pdf_report_id)
        self.assertEqual(len(self._pdf_attachments(invoice)), 1)

    def test_fix_from_the_backend(self):
        """With the session still open, the invoice is fixed in the backend and sent again."""
        self._cfe_error_mode()
        order = self._sell(self._create_config())
        invoice = order.account_move
        self.assertEqual(invoice.l10n_latam_document_type_id, self.env.ref("l10n_uy.dc_e_ticket"))

        invoice.button_draft()
        self.assertEqual(invoice.state, "draft")
        invoice.partner_id = self.partner_local
        self.assertEqual(invoice.l10n_latam_document_type_id, self.env.ref("l10n_uy.dc_e_inv"))
        self.assertEqual(order.partner_id, self.partner_local, "The order follows the customer of its invoice")

        self._demo_mode()
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertIn(invoice.payment_state, ("paid", "in_payment"), "The POS payment is reconciled again")

    def test_fix_after_closing_the_session(self):
        """The session closes with the invoice in error. Fixed and sent again later, it gets the POS payment back."""
        self._cfe_error_mode()
        order = self._sell(self._create_config())
        invoice = order.account_move
        session = order.session_id
        session.close_session_from_ui()
        self.assertEqual(session.state, "closed")

        invoice.button_draft()
        self.assertEqual(invoice.state, "draft")

        self._demo_mode()
        invoice.action_post()
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertIn(invoice.payment_state, ("paid", "in_payment"), "The POS payment is reconciled again")
