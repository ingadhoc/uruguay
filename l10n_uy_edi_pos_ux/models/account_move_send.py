from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _l10n_uy_edi_pos_skip_odoo_pdf(self, invoice):
        """Invoiced from the POS, a Uruguayan e-invoice only has the PDF of Uruware, asked when it is printed."""
        return bool(self.env.context.get("l10n_uy_edi_pos_sale")) and invoice._l10n_uy_edi_pos_is_einvoice()

    @api.model
    def _l10n_uy_edi_pos_odoo_pdf_data(self, invoices_data):
        return {
            invoice: invoice_data
            for invoice, invoice_data in invoices_data.items()
            if not self._l10n_uy_edi_pos_skip_odoo_pdf(invoice)
        }

    @api.model
    def _prepare_invoice_pdf_report(self, invoices_data):
        if to_render := self._l10n_uy_edi_pos_odoo_pdf_data(invoices_data):
            super()._prepare_invoice_pdf_report(to_render)

    @api.model
    def _hook_invoice_document_after_pdf_report_render(self, invoice, invoice_data):
        # Without the Odoo PDF there is nothing to embed the e-invoice XML in (Factur-X of account_edi_ubl_cii)
        if self._l10n_uy_edi_pos_skip_odoo_pdf(invoice):
            return
        return super()._hook_invoice_document_after_pdf_report_render(invoice, invoice_data)

    @api.model
    def _generate_invoice_fallback_documents(self, invoices_data):
        # No proforma either
        if to_render := self._l10n_uy_edi_pos_odoo_pdf_data(invoices_data):
            super()._generate_invoice_fallback_documents(to_render)
