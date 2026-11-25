from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _l10n_uy_edi_pos_skip_odoo_pdf(self, invoice):
        """POC 3: invoiced from the POS, a Uruguayan e-invoice only has the PDF Uruware returned."""
        return self.env.context.get("l10n_uy_edi_pos_no_odoo_pdf") and invoice._l10n_uy_edi_pos_is_einvoice()

    @api.model
    def _prepare_invoice_pdf_report(self, invoices_data):
        to_render = {
            invoice: invoice_data
            for invoice, invoice_data in invoices_data.items()
            if not self._l10n_uy_edi_pos_skip_odoo_pdf(invoice)
        }
        if to_render:
            super()._prepare_invoice_pdf_report(to_render)

    @api.model
    def _hook_invoice_document_after_pdf_report_render(self, invoice, invoice_data):
        # Without the Odoo PDF there is nothing to embed the e-invoice XML in (Factur-X)
        if self._l10n_uy_edi_pos_skip_odoo_pdf(invoice):
            return
        return super()._hook_invoice_document_after_pdf_report_render(invoice, invoice_data)

    @api.model
    def _generate_invoice_fallback_documents(self, invoices_data):
        # No proforma either: the error stays on the invoice, as without the fallback
        to_render = {
            invoice: invoice_data
            for invoice, invoice_data in invoices_data.items()
            if not self._l10n_uy_edi_pos_skip_odoo_pdf(invoice)
        }
        if to_render:
            super()._generate_invoice_fallback_documents(to_render)
