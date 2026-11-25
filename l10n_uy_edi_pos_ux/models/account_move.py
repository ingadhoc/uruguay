from odoo import models
from odoo.addons.point_of_sale.models.account_move import AccountMove as PosAccountMove

if not getattr(PosAccountMove.button_draft, "_l10n_uy_edi_pos_ux", False):
    _pos_button_draft = PosAccountMove.button_draft

    def button_draft(self):
        """The POS refuses to reset an invoice of an open session. An invoice whose CFE failed is fixed from the
        backend, so it can go back to draft anyway: only that guard is skipped, the rest of the chain runs."""
        if self and self == self._l10n_uy_edi_pos_cfe_error():
            return super(PosAccountMove, self).button_draft()
        return _pos_button_draft(self)

    button_draft._l10n_uy_edi_pos_ux = True
    PosAccountMove.button_draft = button_draft


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_uy_edi_pos_is_einvoice(self):
        """Uruguayan e-invoice of a POS sale. While the POS invoices a sale, the order is not linked yet."""
        self.ensure_one()
        return (
            self.country_code == "UY"
            and self.is_sale_document()
            and self.journal_id.l10n_uy_edi_type == "electronic"
            and bool(self.env.context.get("l10n_uy_edi_pos_sale") or self.sudo().pos_order_ids)
        )

    def _l10n_uy_edi_pos_cfe_error(self):
        return self.filtered(lambda m: m.l10n_uy_edi_cfe_state == "error" and m._l10n_uy_edi_pos_is_einvoice())

    def _l10n_uy_edi_pos_without_cfe(self):
        """POS e-invoice that DGI did not validate: it has no legal PDF and none must be rendered."""
        self.ensure_one()
        invoice = self.sudo()
        return invoice._l10n_uy_edi_pos_is_einvoice() and invoice.l10n_uy_edi_cfe_state not in ("received", "accepted")

    def button_draft(self):
        if self.env.context.get("l10n_uy_edi_pos_sale"):
            # The sale goes on: the invoice stays posted with its temporary name and is fixed from the backend
            self -= self._l10n_uy_edi_pos_cfe_error()
            if not self:
                return False
        return super().button_draft()

    def _l10n_uy_edi_get_pdf(self):
        # The PDF of a POS sale is asked to Uruware only when someone prints it (_l10n_uy_edi_pos_get_legal_pdf)
        if self.env.context.get("l10n_uy_edi_pos_sale") and self._l10n_uy_edi_pos_is_einvoice():
            return {}
        return super()._l10n_uy_edi_get_pdf()

    def _l10n_uy_edi_pos_get_legal_pdf(self):
        """Ask Uruware for the PDF of a validated CFE the first time it is needed. It stays on the invoice, so the
        next prints, downloads and portal visits use it without calling Uruware again."""
        for invoice in self.sudo().filtered(
            lambda m: not m.invoice_pdf_report_id and m.l10n_uy_edi_cfe_state in ("received", "accepted")
        ):
            invoice.action_l10n_uy_get_pdf()

    def l10n_uy_edi_pos_download_invoice(self):
        """Called by the POS to print the invoice: the legal PDF, or the error that prevents having one."""
        self.ensure_one()
        invoice = self.sudo()
        if not invoice._l10n_uy_edi_pos_is_einvoice():
            return {"action": self.action_invoice_download_pdf()}
        if invoice._l10n_uy_edi_pos_without_cfe():
            return {
                "error": invoice.l10n_uy_edi_error or self.env._("DGI did not validate this CFE."),
                "message": self.env._(
                    "The tax receipt (CFE) of this sale was not issued because of an error, so there is no legal "
                    "PDF to print. Ask your supervisor to fix the tax receipt from the backend. To do so, give them "
                    "the order number: %(order)s",
                    order=invoice.pos_order_ids[:1].pos_reference or invoice.name,
                ),
            }
        invoice._l10n_uy_edi_pos_get_legal_pdf()
        if not invoice.invoice_pdf_report_id:
            return {
                "error": invoice.l10n_uy_edi_error or "",
                "message": self.env._(
                    "The CFE was issued, but Uruware did not return its PDF. Try again in a few minutes, or print it "
                    "from the invoice in the backend."
                ),
            }
        return {"action": self.action_invoice_download_pdf()}

    def _compute_l10n_latam_document_type(self):
        """A POS invoice whose CFE failed was already posted once, so the document type no longer follows the
        customer. Fixing the customer in the backend must still turn an e-Ticket into an e-Invoice, and the other
        way around."""
        to_fix = self.filtered(
            lambda m: m.state == "draft"
            and m.posted_before
            and m.move_type == "out_invoice"
            and not m.debit_origin_id
            and m.l10n_uy_edi_cfe_state in (False, "error")
            and m._l10n_uy_edi_pos_is_einvoice()
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
            for move in self.filtered(lambda m: m.state == "draft" and m._l10n_uy_edi_pos_is_einvoice()):
                move.sudo().pos_order_ids.partner_id = move.partner_id
        return res

    def _post(self, soft=True):
        res = super()._post(soft=soft)
        if self.env.context.get("l10n_uy_edi_pos_sale"):
            return res
        # An invoice fixed in the backend lost its reconciliation when it went back to draft: posted again, it gets
        # the payments the POS registered.
        for move in res.sudo().filtered(lambda m: m.country_code == "UY" and m.pos_order_ids):
            payment_moves = move.pos_order_ids.payment_ids.account_move_id
            receivable = move.line_ids.filtered(lambda line: line.account_type == "asset_receivable")
            if payment_moves and not any(receivable.mapped("reconciled")):
                move.pos_order_ids[:1]._reconcile_invoice_payments(move, payment_moves)
        return res

    def _generate_and_send(self, force_synchronous=True, allow_fallback_pdf=True, **custom_settings):
        # Without a validated CFE there is nothing to send from the sale: no PDF, no proforma, no mail
        to_send = self
        if self.env.context.get("l10n_uy_edi_pos_sale"):
            to_send -= self._l10n_uy_edi_pos_cfe_error()
        return super(AccountMove, to_send)._generate_and_send(
            force_synchronous=force_synchronous, allow_fallback_pdf=allow_fallback_pdf, **custom_settings
        )
