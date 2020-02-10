from odoo import api, models, fields, _


class AccountInvoice(models.Model):

    _inherit = 'account.invoice'
    l10n_uy_invoice_type = fields.Selection([('cash', 'Cash'), ('credit', 'Credit')], 'Invoice Type', default='cash')

    @api.model
    def _get_available_journal_document_types(self, journal, invoice_type, partner):
        """ This function filter the journal documents types taking into account the partner identification type """
        res = super()._get_available_journal_document_types(journal, invoice_type, partner)
        if journal.localization == 'uruguay' and partner:
            available_types = self.env['account.journal.document.type']
            commercial_partner = partner.commercial_partner_id
            partner_type = dict(
                final_consumer=self.env.ref('l10n_uy.it_dni') + self.env.ref('l10n_uy.it_ci') +
                self.env.ref('l10n_uy.it_pass') + self.env.ref('l10n_uy.it_other'),
                company=self.env.ref('l10n_uy.it_rut'))

            # TODO we can improve this if we separete ticket and invoice tye documents, but we have a problem, need to
            # add a new seperation for dn and cn
            if commercial_partner.main_id_category_id in partner_type['final_consumer']:
                # e-tickets docs
                available_types = [000, 101, 102, 103, 131, 132, 133, 201, 202, 203, 231, 232, 233]
            elif commercial_partner.main_id_category_id in partner_type['company']:
                # e-invoices docs
                available_types = [
                    000, 111, 112, 113, 121, 122, 123, 141, 142, 143, 201, 211, 212, 213, 221, 222, 223, 241, 242, 243]
            else:
                res['available_journal_document_types'] = False
                res['journal_document_type'] = False

            if available_types:
                res['available_journal_document_types'] = res['available_journal_document_types'].filtered(
                    lambda x: int(x.document_type_id.code) in available_types)
                res['journal_document_type'] = res['available_journal_document_types'] and \
                    res['available_journal_document_types'][0]

        return res

    @api.onchange('journal_id', 'partner_id', 'company_id')
    def onchange_available_journal_document_types(self):
        """ Show a message to the user that we are not able to properly show the documents type because not """
        res = self._get_available_journal_document_types(self.journal_id, self.type, self.partner_id)
        self.journal_document_type_id = res['journal_document_type']

        # TODO maybe we should move this to account_document directly, and add a localization field to the document type
        if self.partner_id:
            uy_partner_ids = self.env.ref("l10n_uy.it_nie") + self.env.ref("l10n_uy.it_rut") + \
                self.env.ref("l10n_uy.it_ci") + self.env.ref("l10n_uy.it_other") + self.env.ref("l10n_uy.it_pass") + \
                self.env.ref("l10n_uy.it_dni")
            if not self.partner_id.main_id_category_id or self.partner_id.main_id_category_id not in uy_partner_ids:
                return {'warning': {
                    'title': _('Not Been able to filter the document types'),
                    'message': _('Please set the partner ID type in order to proper filter the document types'),
                }}
