# -*- coding: utf-8 -*-
from collections import OrderedDict
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import pdf


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf_prepare_streams(self, report_ref, data, res_ids=None):
        """ Similar approacho to vendor bills, to use original bill, but in this case we use
        the original pdf that was added when creating the EDI invoice.

        #  'l10n_uy_edi.report_edi_customer_invoice' needed?
        """
        print(" ------ _render_qweb_pdf_prepare_streams")
        import pdb
        pdb.set_trace()

        invoice_reports = ['account.report_invoice', 'account.report_invoice_with_payments']
        if self._get_report(report_ref).report_name not in invoice_reports:
            return super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=res_ids)

        invoices = self.env['account.move'].browse(res_ids)
        uy_edi_invoices = invoices.filtered(lambda x: x.l10n_uy_journal_type == 'electronic' and x.company_id.account_fiscal_country_id.code == 'UY')
        if invoices - uy_edi_invoices:
            collected_streams = super()._render_qweb_pdf_prepare_streams(report_ref, data, res_ids=(invoices - uy_edi_invoices).ids)
        else:
            collected_streams = OrderedDict()

        original_attachments = uy_edi_invoices.message_main_attachment_id
        if not original_attachments:
            raise UserError(_("No Legal PDF document could be found for any of the selected CFE"))

        for invoice in uy_edi_invoices:
            attachment = invoice.message_main_attachment_id
            if attachment:
                stream = pdf.to_pdf_stream(attachment)
                collected_streams[invoice.id] = {
                    'stream': stream,
                    'attachment': attachment,
                }
        return collected_streams
