from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _generate_pos_order_invoice(self):
        """When Uruware rejects the CFE of a POS invoice, do not render the Odoo PDF as a fallback
        and leave the invoice in draft, so it does not stay posted without a valid CFE."""
        if not self.env.context.get("generate_pdf", True) or not (
            self.company_id.account_fiscal_country_id.code == "UY"
            and self.config_id.invoice_journal_id.l10n_uy_edi_type == "electronic"
        ):
            return super()._generate_pos_order_invoice()

        invoice = super(PosOrder, self.with_context(generate_pdf=False))._generate_pos_order_invoice()
        # Same as the core _generate_and_send(), but without the fallback PDF on error and without
        # raising: the error is logged on the invoice chatter.
        self.env["account.move.send"].with_context(skip_invoice_sync=True)._generate_and_send_invoices(
            invoice, allow_raising=False, allow_fallback_pdf=False
        )
        if invoice.l10n_uy_edi_cfe_state not in ("received", "accepted"):
            # point_of_sale forbids resetting to draft an invoice of an open session. Here the invoice
            # never got a valid CFE, so it is detached from the orders while it goes back to draft.
            orders = invoice.sudo().pos_order_ids
            orders.account_move = False
            invoice.button_draft()
            orders.account_move = invoice
        return invoice
