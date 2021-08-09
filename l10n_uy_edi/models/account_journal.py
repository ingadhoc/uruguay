# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    # TODO Tenemos algo que se llama puntos de emision, ver si esto lo podemos configurar aca,
    # seria como el AFIP Pos Number?

    def _update_journal_document_types(self):
        self.ensure_one()
        if self.company_id.country_id.code != 'UY':
            return super()._update_journal_document_types()

        internal_types = ['invoice', 'debit_note', 'credit_note']
        document_types = self.env['l10n_latam.document.type'].search(
            [('internal_type', 'in', internal_types), ('country_id.code', '=', 'UY')])
        document_types = document_types - self.mapped('l10n_ar_sequence_ids.l10n_latam_document_type_id')

        # TODO We are forcing the available documents to the ones we supported by the moment, this part of the code
        # should be removed in future when we add the other documents.
        if self.type == 'sale' and self.l10n_uy_type == 'preprinted':
            document_types = document_types.filtered(lambda x: int(x.code) == 0)
        elif self.type == 'sale' and self.l10n_uy_type == 'electronic':
            document_types = document_types.filtered(lambda x: int(x.code) in [101, 102, 103, 111, 112, 113, 121, 122, 123])
        elif self.type == 'sale' and self.l10n_uy_type == 'contingency':
            document_types = document_types.filtered(lambda x: int(x.code) in [201, 202, 203, 211, 212, 213, 221, 222, 223])
        elif self.type == 'purchase' and self.l10n_uy_type == 'preprinted':
            document_types = document_types.filtered(lambda x: int(x.code) == 0)
        elif self.type == 'purchase' and self.l10n_uy_type == 'electronic':
            document_types = document_types.filtered(lambda x: int(x.code) in [101, 102, 103, 111, 112, 113, 201, 211, 212, 213])
        self._create_document_sequences(document_types)

    @api.onchange('l10n_uy_type')
    def onchange_journal_uy_type(self):
        """ Si el tipo de diario es de contigencia entonces se usara el mismo numero para todos los documentos de ese tipo """
        if self.company_id.country_id.code == 'UY' and self.l10n_latam_use_documents:
            self.l10n_uy_share_sequences = True

    def _get_journal_codes(self):
        self.ensure_one()
        if self.type != 'sale':
            return []
        if self.l10n_uy_type == 'preprinted':
            available_types = [000]
        elif self.l10n_uy_type == 'electronic':
            available_types = [101, 102, 103, 111, 112, 113, 121, 122, 123, 141, 142, 143]
        elif self.l10n_uy_type == 'contingency':
            available_types = [201, 211, 212, 213, 221, 222, 223, 241, 242, 243]
        return available_types
