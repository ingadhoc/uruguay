from collections import OrderedDict
from odoo import models
from odoo.tools import pdf


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """ Similar approach to vendor bills (print original bill), but in this case we use
        the original pdf that was added when creating the EDI invoice """

        # If we are not printing the invoice report then we continue as it is
        invoice_reports = ['account.report_invoice', 'account.report_invoice_with_payments']
        if self._get_report(report_ref).report_name not in invoice_reports:
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        # If we do not have any EDI UY invoice then print the regular report from Odoo
        invoices = self.env['account.move'].browse(res_ids)
        uy_edi_invoices_w_legal_pdf = invoices.filtered(
            lambda x: x.l10n_uy_edi_journal_type == 'electronic'
            and x.company_id.account_fiscal_country_id.code == 'UY'
            and x.invoice_pdf_report_id
        )
        demo_env = {move._l10n_uy_edi_is_demo_env() for move in invoices}

        if not uy_edi_invoices_w_legal_pdf or demo_env == {True}:
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        # If we have both, UY EDI invoices and other invoices we process them separately
        if invoices - uy_edi_invoices_w_legal_pdf:
            collected_streams = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=(invoices - uy_edi_invoices_w_legal_pdf).ids)
        else:
            collected_streams = OrderedDict()

        for invoice in uy_edi_invoices_w_legal_pdf:
            original_attachment = invoice.invoice_pdf_report_id
            stream = pdf.to_pdf_stream(original_attachment)
            collected_streams[invoice.id] = {
                'stream': stream,
                'attachment': original_attachment,
            }

        return collected_streams
