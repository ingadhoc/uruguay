from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_uy_edi_cfe_state = fields.Selection(related="account_move.l10n_uy_edi_cfe_state")
    l10n_uy_edi_error = fields.Text(related="account_move.l10n_uy_edi_error")

    def _reconcile_invoice_payments(self, invoice, payment_moves):
        # A draft invoice (CFE in error) is reconciled when it is posted again.
        if invoice.state != "posted":
            return
        return super()._reconcile_invoice_payments(invoice, payment_moves)

    def _generate_pos_order_invoice(self):
        invoice = super()._generate_pos_order_invoice()
        # POC 5: when the next CFE would fail the same way, stop invoicing until the problem is solved
        for order in self.filtered(lambda o: o.config_id.l10n_uy_cfe_error_flow == "contingency"):
            move = order.account_move.sudo()
            if move._l10n_uy_edi_pos_cfe_error() and move._l10n_uy_edi_pos_needs_contingency():
                order.session_id.sudo()._l10n_uy_edi_pos_enter_contingency(move.l10n_uy_edi_error)
        return invoice

    def read_pos_data(self, data, config):
        # The POS learns in the same sale that its session entered contingency mode
        res = super().read_pos_data(data, config)
        sessions = self.session_id.filtered("invoice_contingency")
        if config and sessions:
            res["pos.session"] = self.env["pos.session"]._load_pos_data_read(sessions, config)
        return res

    def l10n_uy_edi_pos_retry_cfe(self):
        """Called from the POS order list: sends again the CFE of an invoice that DGI did not validate."""
        self.ensure_one()
        invoice = self.sudo().account_move
        if invoice._l10n_uy_edi_pos_cfe_error():
            if invoice.l10n_uy_edi_document_id.connection_error:
                # We do not know whether the CFE reached DGI: ask for its state instead of sending it again
                invoice.l10n_uy_edi_action_update_dgi_state()
            else:
                force_draft = invoice.with_context(l10n_uy_edi_pos_force_draft=True)
                if invoice.state == "posted":
                    force_draft.button_draft()
                invoice.action_post()
                if invoice.l10n_uy_edi_cfe_state in ("received", "accepted"):
                    # Same as a sale that went fine: the invoice gets its PDF and is sent.
                    invoice._generate_and_send()
                elif invoice.state == "posted" and invoice._l10n_uy_edi_pos_flow() == "posted_then_draft":
                    force_draft.button_draft()
        return {
            "state": invoice.state,
            "cfe_state": invoice.l10n_uy_edi_cfe_state,
            "error": invoice.l10n_uy_edi_error or False,
            "name": invoice.name or False,
        }
