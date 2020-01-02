##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class AccountJournal(models.Model):

    _inherit = "account.journal"

    @api.multi
    def _update_journal_document_types(self):
        self.ensure_one()
        if self.localization != 'uruguay':
            return super()._update_journal_document_types()

        if not self.use_documents:
            return True

        internal_types = ['invoice', 'debit_note', 'credit_note']
        document_types = self.env['account.document.type'].search(
            [('internal_type', 'in', internal_types), ('localization', '=', self.localization)])
        document_types = document_types - self.mapped('journal_document_type_ids.document_type_id')

        # TODO We are forcing the available documents to the ones we supported by the moment, this part of the code
        # should be removed in future when we add the other documents.
        if self.type == 'sale':
            document_types = document_types.filtered(lambda x: int(x.code) in [
                000, 101, 102, 103, 111, 112, 113, 121, 122, 123, 201, 202, 203, 211, 212, 213, 221, 222, 223])
        elif self.type == 'purchase':
            document_types = document_types.filtered(lambda x: int(x.code) in [000, 111, 112, 113, 211, 212, 213])

        self._create_document_sequences(document_types)

    def _create_document_sequences(self, document_types):
        """ Create sequences for the current journal and given documents """
        self.ensure_one()
        sequence = 10
        for document_type in document_types:
            sequence_id = False
            if self.type == 'sale':
                sequence_id = self.env['ir.sequence'].create(document_type.get_document_sequence_vals(self)).id
            self.journal_document_type_ids.create({
                'document_type_id': document_type.id,
                'sequence_id': sequence_id,
                'journal_id': self.id,
                'sequence': sequence,
            })
            sequence += 10
        return True
