from odoo import api, fields, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    l10n_uy_contingency_reason = fields.Text(readonly=True)

    def _l10n_uy_edi_pos_unposted_cfe_error(self):
        unposted = (
            self._get_closed_orders()
            .sudo()
            .with_company(self.company_id)
            .account_move.filtered(lambda x: x.state != "posted")
        )
        return unposted, unposted._l10n_uy_edi_pos_cfe_error()

    def _l10n_uy_edi_pos_cfe_error_message(self, invoices):
        lines = [
            "- %s, %s" % (", ".join(invoice.pos_order_ids.mapped("pos_reference")), invoice.partner_id.display_name)
            for invoice in invoices
        ]
        return self.env._(
            "DGI did not validate the CFE of these sales, so their invoices are still in draft:\n%(sales)s\n\n"
            "Retry them from Orders (Retry CFE) before closing the session.",
            sales="\n".join(lines),
        )

    def _cannot_close_session(self, bank_payment_method_diffs=None):
        # The POS shows this message; the error raised later only says "an error has occurred"
        if self.config_id.l10n_uy_cfe_error_flow != "native" and not self.config_id.l10n_uy_allow_close_with_cfe_error:
            cfe_error = self._l10n_uy_edi_pos_unposted_cfe_error()[1]
            if cfe_error:
                return {
                    "successful": False,
                    "title": self.env._("Invoices without CFE"),
                    "message": self._l10n_uy_edi_pos_cfe_error_message(cfe_error),
                    "redirect": False,
                }
        return super()._cannot_close_session(bank_payment_method_diffs=bank_payment_method_diffs)

    def _check_invoices_are_posted(self):
        if self.config_id.l10n_uy_cfe_error_flow != "native":
            unposted, cfe_error = self._l10n_uy_edi_pos_unposted_cfe_error()
            if unposted and unposted == cfe_error:
                if self.config_id.l10n_uy_allow_close_with_cfe_error:
                    return
                raise UserError(self._l10n_uy_edi_pos_cfe_error_message(cfe_error))
        return super()._check_invoices_are_posted()

    def _l10n_uy_edi_pos_enter_contingency(self, reason):
        for session in self.filtered(lambda s: not s.invoice_contingency):
            session.write({"invoice_contingency": True, "l10n_uy_contingency_reason": reason})
            session.message_post(body=self.env._("Contingency mode activated automatically: %s", reason))

    def action_unset_invoice_contingency(self):
        self.l10n_uy_contingency_reason = False
        return super().action_unset_invoice_contingency()

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ["l10n_uy_contingency_reason"]
