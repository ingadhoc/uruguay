# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_uy_type = fields.Selection(
        [('preprinted', 'Preprinted (Traditional)'),
         ('electronic', 'Electronic')],
        string='Invoicing Type', copy=False)

    # TODO Tenemos algo que se llama puntos de emision, ver si esto lo podemos configurar aca,
    # seria como el AFIP Pos Number?

    @api.multi
    def _update_journal_document_types(self):
        self.ensure_one()
        if self.localization != 'uruguay':
            return super()._update_journal_document_types()

        internal_types = ['invoice', 'debit_note', 'credit_note']
        document_types = self.env['account.document.type'].search([('internal_type', 'in', internal_types), ('localization', '=', self.localization)])
        document_types = document_types - self.mapped('journal_document_type_ids.document_type_id')

        # TODO We are forcing the available documents to the ones we supported by the moment, this part of the code
        # should be removed in future when we add the other documents.
        if self.type == 'sale' and self.l10n_uy_type == 'preprinted':
            document_types = document_types.filtered(lambda x: int(x.code) == 0)
        elif self.type == 'sale' and self.l10n_uy_type == 'electronic':
            document_types = document_types.filtered(lambda x: int(x.code) in [101, 102, 103, 111, 112, 113, 121, 122, 123, 201, 202, 203, 211, 212, 213, 221, 222, 223])
        elif self.type == 'purchase' and self.l10n_uy_type == 'preprinted':
            document_types = document_types.filtered(lambda x: int(x.code) == 0)
        elif self.type == 'purchase' and self.l10n_uy_type == 'electronic':
            document_types = document_types.filtered(lambda x: int(x.code) in [101, 102, 103, 111, 112, 113, 201, 211, 212, 213])
        self._create_document_sequences(document_types)
