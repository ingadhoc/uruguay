from odoo.addons.l10n_uy_edi.tests import common
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("-at_install", "post_install", "post_install_l10n", "mock")
class TestRejectedThenAccepted(common.TestUyEdi):
    """DGI can reject a CFE and accept it later (E06: amount over the usual ones for the RUT). The invoice was
    cancelled on the rejection and has to be posted again with the same CFE, not issued again."""

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

    def _rejected_invoice(self):
        invoice = self._create_move().with_context(l10n_uy_skip_edi_send=True)
        invoice.action_post()
        self._mock_send_and_print(invoice, "mock_90_invoice_received")
        self._mock_update_dgi_state(invoice, "mock_invoice_rejected")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "rejected")
        self.assertEqual(invoice.state, "cancel")
        return invoice

    def test_10_rejected_invoice_is_posted_again_when_accepted(self):
        invoice = self._rejected_invoice()
        edi_doc = invoice.l10n_uy_edi_document_id
        number = invoice.name

        self._mock_update_dgi_state(invoice, "mock_90_invoice_received")

        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")
        self.assertEqual(invoice.state, "posted", "The accepted invoice was left cancelled")
        self.assertEqual(invoice.name, number, "The invoice lost the number of its CFE")
        self.assertEqual(invoice.l10n_uy_edi_document_id, edi_doc, "A new CFE was created")
        self.assertFalse(invoice.l10n_uy_edi_error)

    def test_20_still_rejected_invoice_is_not_cancelled_again(self):
        invoice = self._rejected_invoice()
        cancel_notes = invoice.message_ids.filtered(lambda m: "automatically cancel" in (m.body or ""))

        self._mock_update_dgi_state(invoice, "mock_invoice_rejected")

        self.assertEqual(invoice.state, "cancel")
        self.assertEqual(
            invoice.message_ids.filtered(lambda m: "automatically cancel" in (m.body or "")),
            cancel_notes,
            "The rejection was processed twice",
        )

    def test_30_accepted_invoice_cannot_be_updated(self):
        invoice = self._create_move().with_context(l10n_uy_skip_edi_send=True)
        invoice.action_post()
        self._mock_send_and_print(invoice, "mock_90_invoice_received")
        self._mock_update_dgi_state(invoice, "mock_90_invoice_received")
        self.assertEqual(invoice.l10n_uy_edi_cfe_state, "accepted")

        with self.assertRaisesRegex(UserError, "accepted invoice"):
            invoice.l10n_uy_edi_action_update_dgi_state()
