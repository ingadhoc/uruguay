from odoo import models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _generate_pos_order_invoice(self):
        """Send the CFE without rendering the Odoo PDF as a fallback. If it fails, the invoice goes back
        to draft. If Uruware rejected it (e.g. no numbering available), the session also enters
        contingency mode (pos_ux): the next orders are not invoiced until the cashier ends it, and the
        pending invoices are generated afterwards."""
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
            # Uruware answered with an error (e.g. no numbering available): the next orders would fail
            # too, so the session enters contingency. A data error caught before sending (e.g. missing
            # receiver data) only affects this order.
            if invoice.l10n_uy_edi_document_id:
                self.session_id.sudo()._l10n_uy_pos_enter_contingency(invoice.l10n_uy_edi_error)
            # point_of_sale forbids resetting to draft an invoice of an open session. Here the invoice
            # never got a valid CFE, so it is detached from the orders while it goes back to draft.
            orders = invoice.sudo().pos_order_ids
            orders.account_move = False
            invoice.button_draft()
            orders.account_move = invoice
        return invoice

    def read_pos_data(self, data, config):
        # Send the session back to the POS, so it learns in the same sync that it entered contingency
        res = super().read_pos_data(data, config)
        sessions = self.session_id.filtered("invoice_contingency")
        if config and sessions:
            res["pos.session"] = self.env["pos.session"]._load_pos_data_read(sessions, config)
        return res
