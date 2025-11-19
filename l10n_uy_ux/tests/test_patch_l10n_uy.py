from odoo import Command, tools
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestPatchDummy(common.TransactionCase):
    def test_dummy(self):
        # a trivial test so the test runner reports >0 tests (avoids the 0-tests warning)
        self.assertTrue(True)


# Only apply the patch while running tests
if tools.config.get("test_enable"):
    from odoo.addons.account.tests.common import AccountTestInvoicingCommon
    from odoo.addons.l10n_uy.tests.test_doc_types import TestDocTypes

    @classmethod
    @AccountTestInvoicingCommon.setup_country("uy")
    def setUpClass_patch(cls):
        """Patcheamos el setUp de l10n_uy porque al enviar las facturas a DGI automáticamente al confirmarlas, fallan las validaciones de VAT
        porque no está seteado a esta altura"""
        super(AccountTestInvoicingCommon, cls).setUpClass()
        original_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.env.company.id)]
        )
        original_journal.copy(
            {
                "name": "Customer Invoices Manual",
                "l10n_uy_edi_type": "manual",
                "sequence": 1,
            }
        )

        service_vat_22 = cls.env["product.product"].create(
            {
                "name": "Virtual Home Staging (VAT 22)",
                "list_price": 38.25,
                "standard_price": 45.5,
                "type": "service",
                "default_code": "VAT 22",
            }
        )

        cls.invoice = cls.env["account.move"].create(
            {
                "partner_id": cls.env["res.partner"].create({"name": "test partner UY"}).id,
                "move_type": "out_invoice",
                "l10n_latam_document_type_id": cls.env.ref("l10n_uy.dc_e_inv_exp").id,
                "l10n_latam_document_number": "AA0000001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": service_vat_22.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        cls.invoice.action_post()

    def test_credit_note_patch(self):
        self.assertEqual(self.invoice.l10n_latam_document_type_id.code, "121", "Not Export e-Invoice")

        refund_wizard = (
            self.env["account.move.reversal"]
            .with_context({"active_ids": self.invoice.ids, "active_model": "account.move"})
            .create(
                {
                    "reason": "Mercadería defectuosa",
                    "journal_id": self.invoice.journal_id.id,
                }
            )
        )
        res = refund_wizard.refund_moves()
        refund = self.env["account.move"].browse(res["res_id"])

        self.assertEqual(
            refund.l10n_latam_document_type_id.code,
            "122",
            "Not Export e-Invoice Credit Note",
        )
        expected_docs = ["122"] if refund.journal_id.l10n_uy_edi_type == "electronic" else ["122", "222"]
        self.assertEqual(
            refund.l10n_latam_available_document_type_ids.mapped("code"),
            expected_docs,
            "Bad Domain",
        )

    def test_debit_note_patch(self):
        self.assertEqual(
            self.invoice.l10n_latam_document_type_id.code,
            "121",
            "Not Export e-Invoice",
        )

        debit_note_wizard = (
            self.env["account.debit.note"]
            .with_context({"active_ids": self.invoice.ids, "active_model": "account.move"})
            .create(
                {
                    "reason": "Mercadería defectuosa",
                }
            )
        )
        res = debit_note_wizard.create_debit()
        debit_note = self.env["account.move"].browse(res["res_id"])

        self.assertEqual(
            debit_note.l10n_latam_document_type_id.code,
            "123",
            "Not Export e-Invoice Debit Note",
        )
        expected_docs = ["123"] if debit_note.journal_id.l10n_uy_edi_type == "electronic" else ["123", "223"]
        self.assertEqual(
            debit_note.l10n_latam_available_document_type_ids.mapped("code"),
            expected_docs,
            "Bad Domain",
        )

    def propagate(method1, method2):
        if method1:
            for attr in ("_returns",):
                if hasattr(method1, attr) and not hasattr(method2, attr):
                    setattr(method2, attr, getattr(method1, attr))
        return method2

    def _patch_method(cls, name, method):
        origin = getattr(cls, name)
        method.origin = origin
        wrapped = propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    _patch_method(TestDocTypes, "setUpClass", setUpClass_patch)
    _patch_method(TestDocTypes, "test_credit_note", test_credit_note_patch)
    _patch_method(TestDocTypes, "test_debit_note", test_debit_note_patch)
