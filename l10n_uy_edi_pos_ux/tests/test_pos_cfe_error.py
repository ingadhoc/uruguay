from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestPosCfeErrorCommon


@tagged("-at_install", "post_install", "post_install_l10n")
class TestPosCfeError(TestPosCfeErrorCommon):
    def test_current_flow_posts_without_number(self):
        """Baseline: the invoice stays posted with the CFE in error, which is what the POCs change."""
        config = self._create_config("native", l10n_uy_simulate_cfe_error=True)
        invoice = self._sell(config).account_move
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertFalse(invoice._l10n_uy_edi_pos_hide_printable())

    def test_poc1_draft_until_retry(self):
        config = self._create_config("draft", l10n_uy_simulate_cfe_error=True)
        order = self._sell(config)
        invoice = order.account_move
        self.assertEqual(order.state, "done")
        self.assertEqual(invoice.state, "draft")
        self.assertFalse(invoice.name)
        self.assertIn("CAE", invoice.l10n_uy_edi_error)
        self.assertEqual(invoice.payment_state, "not_paid", "The payment is reconciled once the CFE is validated")
        self.assertFalse(self._pdf_attachments(invoice), "No PDF nor proforma without a validated CFE")
        self.assertFalse(invoice.l10n_uy_edi_pos_pdf_status()["can_download"])

        result = order.l10n_uy_edi_pos_retry_cfe()
        self.assertEqual(result["cfe_state"], "error", "The CAE is still not valid")
        self.assertEqual(invoice.state, "draft")

        config.l10n_uy_simulate_cfe_error = False
        result = order.l10n_uy_edi_pos_retry_cfe()
        self.assertEqual(result["cfe_state"], "accepted")
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.name)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

    def test_poc2_back_to_draft_paid(self):
        config = self._create_config("posted_then_draft", l10n_uy_simulate_cfe_error=True)
        invoice = self._sell(config).account_move
        self.assertEqual(invoice.state, "draft")
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertFalse(self._pdf_attachments(invoice))

    def test_poc3_no_odoo_pdf(self):
        config = self._create_config("no_odoo_pdf")
        invoice = self._sell(config).account_move
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertFalse(invoice.invoice_pdf_report_id, "Only Uruware's PDF, never one rendered by Odoo")
        status = invoice.l10n_uy_edi_pos_pdf_status()
        self.assertFalse(status["can_download"])
        self.assertIn("Uruware", status["message"])

        config.l10n_uy_simulate_cfe_error = True
        invoice = self._sell(config).account_move
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertFalse(self._pdf_attachments(invoice))

    def test_poc4_posted_without_pdf(self):
        config = self._create_config("posted_no_pdf", l10n_uy_simulate_cfe_error=True)
        order = self._sell(config)
        invoice = order.account_move
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertFalse(self._pdf_attachments(invoice))
        self.assertTrue(invoice._l10n_uy_edi_pos_hide_printable())

        config.l10n_uy_simulate_cfe_error = False
        order.l10n_uy_edi_pos_retry_cfe()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertTrue(invoice.invoice_pdf_report_id)
        self.assertTrue(invoice.l10n_uy_edi_pos_pdf_status()["can_download"])

    def test_poc5_contingency_on_cae_error(self):
        config = self._create_config("contingency", l10n_uy_simulate_cfe_error=True)
        invoice = self._sell(config).account_move
        session = config.current_session_id
        self.assertEqual(invoice.state, "draft")
        self.assertTrue(session.invoice_contingency)
        self.assertIn("CAE", session.l10n_uy_contingency_reason)

        next_order = self._sell(config)
        self.assertFalse(next_order.account_move, "In contingency mode the sales are invoiced afterwards")

    def test_poc5_no_contingency_on_data_error(self):
        """A customer without address only affects its own sale: it is fixed from the POS and retried."""
        config = self._create_config("contingency")
        customer = self.partner_local.copy({"street": False, "city": False, "state_id": False})
        order = self._sell(config, partner=customer)
        invoice = order.account_move
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertFalse(config.current_session_id.invoice_contingency)

        customer.write({"street": "Bach 0", "city": "Aeroparque", "state_id": self.env.ref("base.state_uy_02").id})
        order.l10n_uy_edi_pos_retry_cfe()
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertEqual(invoice.l10n_latam_document_type_id, self.env.ref("l10n_uy.dc_e_inv"))

    def test_fix_customer_of_draft_invoice(self):
        """From final consumer to a customer with RUT: the e-Ticket turns into an e-Invoice and the order follows."""
        config = self._create_config("draft", l10n_uy_simulate_cfe_error=True)
        order = self._sell(config)
        invoice = order.account_move
        self.assertEqual(invoice.l10n_latam_document_type_id, self.env.ref("l10n_uy.dc_e_ticket"))
        invoice.partner_id = self.partner_local
        self.assertEqual(invoice.l10n_latam_document_type_id, self.env.ref("l10n_uy.dc_e_inv"))
        self.assertEqual(order.partner_id, self.partner_local)

    def test_close_session_with_cfe_error(self):
        config = self._create_config("draft", l10n_uy_simulate_cfe_error=True)
        order = self._sell(config)
        session = config.current_session_id
        result = session._cannot_close_session()
        self.assertFalse(result["successful"])
        self.assertIn(order.pos_reference, result["message"])
        with self.assertRaisesRegex(UserError, "DGI did not validate"):
            session._check_invoices_are_posted()

        config.l10n_uy_allow_close_with_cfe_error = True
        self.assertFalse(session._cannot_close_session())
        session._check_invoices_are_posted()
