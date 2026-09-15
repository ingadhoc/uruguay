from unittest.mock import patch

from odoo.addons.l10n_uy_edi.tests import common
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("-at_install", "post_install", "post_install_l10n", "mock")
class TestConnectionError(common.TestUyEdi):
    """A transport failure against Uruware says nothing about the CFE: it must not overwrite a state given by
    DGI, and it must not enable a second CFE for an invoice whose first one may already be there."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_uy.write(
            {
                "l10n_uy_edi_ucfe_env": "testing",
                "l10n_uy_edi_ucfe_password": "password_xxx",
                "l10n_uy_edi_ucfe_commerce_code": "commerce_xxx",
                "l10n_uy_edi_ucfe_terminal_code": "terminal_xxx",
            }
        )

    def _mock_inbox(self, response_file=False, exception=None):
        """Patch the call to Uruware, either with a canned response or with a connection that never got there"""
        return patch(
            f"{self.utils_path}._ucfe_inbox",
            return_value=self._mocked_response(response_file, exception=exception),
        )

    def _create_uy_move(self):
        # l10n_uy_ux sends to DGI from _post: the context lets a test post without sending
        return self._create_move().with_context(l10n_uy_skip_edi_send=True)

    def _invoice_with_connection_error(self):
        """A posted invoice whose CFE was cut on its way to Uruware: the state the bug leaves behind"""
        invoice = self._create_uy_move()
        invoice.action_post()
        with self.assertRaisesRegex(UserError, "Timeout"):
            self._mock_send_and_print(invoice, exception="Timeout", expected_xml_file="NO_RESPONSE")
        return invoice

    def test_10_connection_error_does_not_degrade_dgi_state(self):
        """A failed status query must not turn a CFE already answered by DGI into an error"""
        invoice = self._create_uy_move()
        invoice.action_post()
        self._mock_send_and_print(invoice, "mock_90_invoice_received")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "received")

        with self._mock_inbox(exception="Timeout"):
            invoice.l10n_uy_edi_action_update_dgi_state()

        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "received", "A transport failure degraded the CFE state")
        self.assertFalse(invoice.l10n_uy_edi_error, "The connection problem was written as a CFE error")
        self.assertFalse(invoice.l10n_uy_edi_document_id.connection_error)
        self.assertTrue(
            invoice.message_ids.filtered(lambda m: "could not be refreshed" in (m.body or "")),
            "The failed call was not reported in the chatter",
        )

    def test_20_connection_error_on_send_blocks_resend(self):
        """If the send fails on transport we do not know whether the CFE reached DGI: it cannot be sent again"""
        invoice = self._invoice_with_connection_error()

        edi_doc = invoice.l10n_uy_edi_document_id
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")
        self.assertTrue(edi_doc.connection_error)
        self.assertFalse(edi_doc._can_edit(), "The CFE can be edited or sent again after a transport failure")
        self.assertFalse(invoice.l10n_uy_edi_is_needed, "The invoice is still offered to be e-invoiced again")

        with self.assertRaisesRegex(UserError, "cannot be sent again"):
            invoice._l10n_uy_edi_send()
        self.assertEqual(invoice.l10n_uy_edi_document_id, edi_doc, "A second CFE was issued for the same invoice")

    def test_30_post_keeps_the_invoice_and_its_document(self):
        """Posting is what sends to DGI here: on a connection failure the invoice must not go back to draft
        (that is the short path to a duplicate) and its document must survive the post"""
        invoice = self._create_move()
        with self._mock_inbox(exception="Timeout"):
            invoice.action_post()

        self.assertEqual(invoice.state, "posted", "The invoice went back to draft, which invites a resend")
        self.assertTrue(invoice.l10n_uy_edi_document_id, "The document was dropped when the invoice was posted")
        self.assertTrue(invoice.l10n_uy_edi_document_id.connection_error)
        self.assertFalse(invoice.l10n_uy_edi_is_needed)

    def test_40_update_dgi_state_is_allowed_after_a_connection_error(self):
        """The button is the manual way out, so it cannot be blocked for the state it has to get out of"""
        invoice = self._invoice_with_connection_error()

        self._mock_update_dgi_state(invoice, "mock_90_invoice_received")

        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertFalse(invoice.l10n_uy_edi_document_id.connection_error)

    def test_50_cron_recovers_after_a_connection_error(self):
        """The scheduled action queries again what a transport failure left in error, and recovers it"""
        invoice = self._invoice_with_connection_error()
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "error")

        with self._mock_inbox("mock_90_invoice_received_status"):
            self.env["account.move"]._l10n_uy_edi_cron_update_dgi_status()

        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted", "The cron did not recover the CFE")
        self.assertFalse(invoice.l10n_uy_edi_document_id.connection_error)
        self.assertFalse(invoice.l10n_uy_edi_error)
