from odoo import Command
from odoo.addons.l10n_uy_edi.tests import common
from odoo.tests import tagged


@tagged("-at_install", "post_install", "post_install_l10n")
class TestSwitchMoveType(common.TestUyEdi):
    """A negative invoice switched to a credit note (what sale does when invoicing a delivery return) must be sent
    to DGI when posted, as any other credit note."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_vat_0 = cls.env["product.product"].create(
            {"name": "Exempt product", "type": "service", "taxes_id": [Command.set(cls.tax_0.ids)]}
        )

    def test_switched_credit_note_is_sent_to_dgi(self):
        original = self._create_move(
            invoice_line_ids=[Command.create({"product_id": self.product_vat_0.id, "price_unit": 100.0})]
        )
        original.action_post()
        self.assertEqual(original.l10n_uy_edi_cfe_state, "accepted")

        credit_note = self._create_move(
            invoice_line_ids=[
                Command.create({"product_id": self.product_vat_0.id, "quantity": -1.0, "price_unit": 100.0})
            ]
        )
        credit_note.action_switch_move_type()
        credit_note.reversed_entry_id = original
        credit_note.action_post()

        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.state, "posted")
        self.assertEqual(credit_note.l10n_uy_edi_cfe_state, "accepted", "The credit note was posted without CFE")
        self.assertEqual(credit_note.name, "e-NCTK DE%07d" % credit_note.id, "The number was not given by DGI")
