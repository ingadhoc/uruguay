import re

from odoo import models
from odoo.addons.point_of_sale.models.account_move import AccountMove as PosAccountMove

# Flows where an invoice whose CFE failed does not go through the sending (no PDF, no proforma, no mail)
FLOWS_WITHOUT_SENDING_ON_ERROR = ("draft", "posted_then_draft", "posted_no_pdf", "contingency")
# Flows where the invoice goes back to draft while it is posted, with the session still open
FLOWS_DRAFT_ON_POST = ("draft", "contingency")
SIMULATED_ERROR = (
    "CODE 01: (PoC simulation) There is no valid CAE for this document type: it expired or ran out of numbers."
)
CONTINGENCY_ERROR = re.compile(r"\bCAE\b|numeraci|numbering|\bran out of numbers\b", re.IGNORECASE)

if not getattr(PosAccountMove.button_draft, "_l10n_uy_edi_pos_ux", False):
    _pos_button_draft = PosAccountMove.button_draft

    def button_draft(self):
        """The POS refuses to reset an invoice of an open session; a CFE in error must go back to draft anyway.

        Only that guard is skipped: the rest of the chain runs (l10n_uy_edi clears the temporary name there).
        """
        if self.env.context.get("l10n_uy_edi_pos_force_draft"):
            return super(PosAccountMove, self).button_draft()
        return _pos_button_draft(self)

    button_draft._l10n_uy_edi_pos_ux = True
    PosAccountMove.button_draft = button_draft


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_uy_edi_pos_flow(self):
        self.ensure_one()
        return self.sudo().pos_order_ids[:1].config_id.l10n_uy_cfe_error_flow or "native"

    def _l10n_uy_edi_pos_is_einvoice(self):
        self.ensure_one()
        return (
            self.country_code == "UY"
            and self.is_sale_document()
            and self.journal_id.l10n_uy_edi_type == "electronic"
            and bool(self.sudo().pos_order_ids)
        )

    def _l10n_uy_edi_pos_cfe_error(self):
        return self.filtered(
            lambda m: m.l10n_uy_edi_is_needed and m.sudo().pos_order_ids and m.l10n_uy_edi_cfe_state == "error"
        )

    def _l10n_uy_edi_pos_needs_contingency(self):
        """True when the next CFE would fail the same way: the CAE expired or ran out of numbers, or Uruware does
        not answer. A data error (customer, products) only affects this sale.

        The CAE errors are told apart by the text Uruware returns: PoC criterion, to be checked against real answers.
        """
        self.ensure_one()
        document = self.l10n_uy_edi_document_id
        return bool(document.connection_error or CONTINGENCY_ERROR.search(self.l10n_uy_edi_error or ""))

    def _l10n_uy_edi_pos_hide_printable(self):
        """Without the PDF of a validated CFE, the customer must not get a proforma from the portal."""
        self.ensure_one()
        invoice = self.sudo()
        return (
            invoice._l10n_uy_edi_pos_is_einvoice()
            and invoice._l10n_uy_edi_pos_flow() != "native"
            and not invoice.invoice_pdf_report_id
        )

    def l10n_uy_edi_pos_pdf_status(self):
        """Called by the POS before downloading the invoice: without a legal PDF the download would render a
        proforma, so it warns instead."""
        self.ensure_one()
        invoice = self.sudo()
        if not invoice._l10n_uy_edi_pos_is_einvoice() or invoice._l10n_uy_edi_pos_flow() == "native":
            return {"can_download": True}
        if invoice.l10n_uy_edi_cfe_state not in ("received", "accepted"):
            return {
                "can_download": False,
                "title": self.env._("Invoice PDF not available"),
                "message": self.env._("DGI did not validate this invoice yet. Retry the CFE first."),
            }
        if not invoice.invoice_pdf_report_id:
            return {
                "can_download": False,
                "title": self.env._("Invoice PDF not available"),
                "message": self.env._(
                    "The invoice was created, but Uruware did not return its PDF. It can be printed from the invoice "
                    "once Uruware returns it."
                ),
            }
        return {"can_download": True}

    def _l10n_uy_edi_pos_simulate_error(self):
        self.ensure_one()
        return (
            self.company_id.l10n_uy_edi_ucfe_env == "demo"
            and self.sudo().pos_order_ids[:1].config_id.l10n_uy_simulate_cfe_error
        )

    def _l10n_uy_edi_dummy_validation(self):
        # In demo mode Uruware is not called: answer with the error it gives when the CAE is not valid any more
        if self._l10n_uy_edi_pos_simulate_error():
            self.l10n_uy_edi_document_id.write({"state": "error", "message": SIMULATED_ERROR})
            return self.env["ir.attachment"]
        return super()._l10n_uy_edi_dummy_validation()

    def _compute_l10n_latam_document_type(self):
        """A POS invoice whose CFE failed was already posted once, so the document type no longer follows the
        customer. Fixing the customer must still turn an e-Ticket into an e-Invoice, and the other way around."""
        to_fix = self.filtered(
            lambda m: m.state == "draft"
            and m.posted_before
            and m.move_type == "out_invoice"
            and not m.debit_origin_id
            and m.l10n_uy_edi_cfe_state in (False, "error")
            and m._l10n_uy_edi_pos_is_einvoice()
            and m._l10n_uy_edi_pos_flow() != "native"
        )
        rut = self.env.ref("l10n_uy.it_rut")
        for move in to_fix:
            is_rut = move.partner_id.l10n_latam_identification_type_id == rut
            move.l10n_latam_document_type_id = self.env.ref("l10n_uy.dc_e_inv" if is_rut else "l10n_uy.dc_e_ticket")
        return super(AccountMove, self - to_fix)._compute_l10n_latam_document_type()

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals:
            # The order follows the customer fixed on its invoice, so the POS shows the right one
            for move in self.filtered(
                lambda m: m.state == "draft"
                and m._l10n_uy_edi_pos_is_einvoice()
                and m._l10n_uy_edi_pos_flow() != "native"
            ):
                move.sudo().pos_order_ids.partner_id = move.partner_id
        return res

    def _post(self, soft=True):
        if any(move._l10n_uy_edi_pos_flow() in FLOWS_DRAFT_ON_POST for move in self):
            self = self.with_context(l10n_uy_edi_pos_force_draft=True)
        res = super()._post(soft=soft)
        # An invoice re-posted once its CFE is accepted gets the payments the POS registered when it was in error.
        for move in res.sudo().filtered(lambda m: m.country_code == "UY" and m.pos_order_ids):
            payment_moves = move.pos_order_ids.payment_ids.account_move_id
            receivable = move.line_ids.filtered(lambda line: line.account_type == "asset_receivable")
            if payment_moves and not any(receivable.mapped("reconciled")):
                move.pos_order_ids[:1]._reconcile_invoice_payments(move, payment_moves)
        return res

    def _generate_and_send(self, force_synchronous=True, allow_fallback_pdf=True, **custom_settings):
        cfe_error = self._l10n_uy_edi_pos_cfe_error().filtered(
            lambda m: m._l10n_uy_edi_pos_flow() in FLOWS_WITHOUT_SENDING_ON_ERROR
        )
        cfe_error.filtered(
            lambda m: m.state == "posted" and m._l10n_uy_edi_pos_flow() == "posted_then_draft"
        ).with_context(l10n_uy_edi_pos_force_draft=True).button_draft()
        to_send = self - cfe_error
        if any(move._l10n_uy_edi_pos_flow() == "no_odoo_pdf" for move in to_send):
            to_send = to_send.with_context(l10n_uy_edi_pos_no_odoo_pdf=True)
        return super(AccountMove, to_send)._generate_and_send(
            force_synchronous=force_synchronous, allow_fallback_pdf=allow_fallback_pdf, **custom_settings
        )
