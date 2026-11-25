from random import randint

from odoo import fields
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi


class TestPosCfeErrorCommon(TestUyEdi):
    """A UY company with Uruware in demo mode; the DGI error is the simulated one (expired CAE, no numbering)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_uy.l10n_uy_edi_ucfe_env = "demo"
        cls.env.user.group_ids |= cls.env.ref("point_of_sale.group_pos_manager")
        cls.final_consumer = cls.env.ref("l10n_uy.partner_cfu")
        cls.product = cls.product_vat_22
        cls.product.write({"available_in_pos": True, "name": "PoC product"})
        cls.pos_receivable = cls.copy_account(
            cls.company_uy.account_default_pos_receivable_account_id, {"name": "POS Receivable"}
        )

    def _create_config(self, flow, **values):
        cash_journal = self.env["account.journal"].create(
            {"name": f"Cash {flow}", "type": "cash", "code": f"T{randint(1000, 9999)}"}
        )
        payment_method = self.env["pos.payment.method"].create(
            {"name": "Cash", "journal_id": cash_journal.id, "receivable_account_id": self.pos_receivable.id}
        )
        return self.env["pos.config"].create(
            {
                "name": f"PoC {flow}",
                "invoice_journal_id": self.company_data["default_journal_sale"].id,
                "payment_method_ids": [(6, 0, payment_method.ids)],
                "l10n_uy_cfe_error_flow": flow,
                **values,
            }
        )

    def _sell(self, config, partner=None, to_invoice=True):
        """Same payload the POS sends when the cashier validates a paid sale."""
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        partner = partner or self.final_consumer
        tax = self.product.taxes_id
        price = self.product.lst_price
        totals = tax.compute_all(price, session.currency_id, 1)
        uuid = f"test-80088-{randint(1, 10**9)}"
        order = {
            "amount_paid": totals["total_included"],
            "amount_return": 0,
            "amount_tax": totals["total_included"] - totals["total_excluded"],
            "amount_total": totals["total_included"],
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "pricelist_id": config.pricelist_id.id,
            "name": f"Order {uuid}",
            "last_order_preparation_change": "{}",
            "lines": [
                (
                    0,
                    0,
                    {
                        "id": randint(1, 10**6),
                        "pack_lot_ids": [],
                        "price_unit": price,
                        "product_id": self.product.id,
                        "price_subtotal": totals["total_excluded"],
                        "price_subtotal_incl": totals["total_included"],
                        "qty": 1,
                        "tax_ids": [(6, 0, tax.ids)],
                    },
                )
            ],
            "partner_id": partner.id,
            "session_id": session.id,
            "payment_ids": [
                (
                    0,
                    0,
                    {
                        "amount": totals["total_included"],
                        "name": fields.Datetime.now(),
                        "payment_method_id": config.payment_method_ids[:1].id,
                    },
                )
            ],
            "uuid": uuid,
            "user_id": self.env.uid,
            "to_invoice": to_invoice,
            "state": "paid",
        }
        self.env["pos.order"].sync_from_ui([order])
        return self.env["pos.order"].search([("uuid", "=", uuid)])

    def _pdf_attachments(self, invoice):
        return self.env["ir.attachment"].search(
            [("res_model", "=", "account.move"), ("res_id", "=", invoice.id), ("name", "=ilike", "%.pdf")]
        )
