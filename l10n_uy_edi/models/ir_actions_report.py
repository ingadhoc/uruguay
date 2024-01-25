# -*- coding: utf-8 -*-
from collections import OrderedDict
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import pdf


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """ Similar approach to vendor bills, to use original bill,
        but in this case we use the original pdf that was added when
        creating the EDI invoice, """

        # If we are not printing the invoice report then we continue as it is
        invoice_reports = ['account.report_invoice', 'account.report_invoice_with_payments']
        if self._get_report(report_ref).report_name not in invoice_reports:
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        # If we do not have any EDI UY invoice then print the regular report from Odoo
        invoices = self.env['account.move'].browse(res_ids)
        uy_edi_invoices = invoices.filtered(
            lambda x: x.l10n_uy_journal_type == 'electronic'
            and x.company_id.account_fiscal_country_id.code == 'UY')
        if not uy_edi_invoices:
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        # If we have both, UY EDI invoices and other invoices we process then separately
        if invoices - uy_edi_invoices:
            collected_streams = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=(invoices - uy_edi_invoices).ids)
        else:
            collected_streams = OrderedDict()

        for invoice in uy_edi_invoices:
            original_attachment = invoice.l10n_uy_cfe_pdf
            if not original_attachment:
                raise UserError(_("No Legal PDF document could be found for the selected CFE %s") % invoice.display_name)

            stream = pdf.to_pdf_stream(original_attachment)
            collected_streams[invoice.id] = {
                'stream': stream,
                'attachment': original_attachment,
            }

        return collected_streams
