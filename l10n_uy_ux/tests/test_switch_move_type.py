from odoo import Command
from odoo.addons.l10n_uy_edi.tests import common
from odoo.tests import tagged


@tagged("-at_install", "post_install", "post_install_l10n")
class TestSwitchMoveType(common.TestUyEdi):
    """Sale invoices a delivery return as a negative invoice and switches it to a CN with action_switch_move_type(),
    without origin document.

    - The CN knows it is a UY e-invoice even if country_code reads empty during the switch: it is never posted with
      an Odoo number and without CFE.
    - Without origin document nor sale link, it stays in draft with the DGI error.
    - Linked to the sale order, it reports the invoice of the same lines as reference and DGI accepts it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Exempt lines: with 22% VAT a later write of the lines recomputes the EDI flag and hides the bug
        cls.product_vat_0 = cls.env["product.product"].create(
            {"name": "Exempt product", "type": "service", "taxes_id": [Command.set(cls.tax_0.ids)]}
        )

    def _create_switched_credit_note(self, **line_vals):
        credit_note = self._create_move(
            invoice_line_ids=[
                Command.create(
                    {"product_id": self.product_vat_0.id, "quantity": -1.0, "price_unit": 100.0, **line_vals}
                )
            ]
        )
        credit_note.action_switch_move_type()
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertFalse(credit_note.reversed_entry_id)
        return credit_note

    def test_credit_note_from_delivery_return(self):
        with self.subTest(
            "without origin nor sale, the CN is not posted without CFE: it stays in draft with the DGI error"
        ):
            credit_note = self._create_switched_credit_note()
            credit_note.action_post()
            self.assertEqual(credit_note.state, "draft", "The credit note was posted without CFE")
            self.assertEqual(credit_note.l10n_uy_edi_cfe_state, "error")
            self.assertIn("the original document should be informed", credit_note.message_ids[:1].body)

        if "sale_line_ids" not in self.env["account.move.line"]._fields:
            self.skipTest("The sale link requires the sale module")

        self.env.user.group_ids |= self.env.ref("sales_team.group_sale_salesman")
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_local_tk.id,
                "company_id": self.company_uy.id,
                "order_line": [Command.create({"product_id": self.product_vat_0.id, "price_unit": 100.0})],
            }
        )
        order.action_confirm()
        # Linked by hand instead of order._create_invoices(): what can be invoiced depends on the invoicing
        # policy, that other modules change (e.g. by sale order type), and the lookup only needs the link
        sale_link = {"sale_line_ids": [Command.set(order.order_line.ids)]}
        original = self._create_move(
            invoice_line_ids=[
                Command.create({"product_id": self.product_vat_0.id, "price_unit": 100.0, **sale_link}),
            ]
        )
        original.action_post()
        self.assertEqual(original.l10n_uy_edi_cfe_state, "accepted")

        with self.subTest("linked to the sale order, the CN reports the original invoice and DGI accepts it"):
            credit_note = self._create_switched_credit_note(**sale_link)
            credit_note.action_post()
            self.assertEqual(credit_note.state, "posted")
            self.assertEqual(credit_note.l10n_uy_edi_cfe_state, "accepted", "The credit note was posted without CFE")
            self.assertEqual(credit_note.name, "e-NCTK DE%07d" % credit_note.id, "The number was not given by DGI")
            self.assertEqual(credit_note._l10n_uy_edi_found_related_cfe(), original)
