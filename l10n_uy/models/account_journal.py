##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class AccountJournal(models.Model):

    _inherit = "account.journal"

    l10n_uy_type = fields.Selection(
        [('preprinted', 'Preprinted (Traditional)'),
         ('electronic', 'Electronic'),
         ('contingency', 'Contingency')],
        string='Invoicing Type', copy=False)

    l10n_uy_sequence_ids = fields.One2many('ir.sequence', 'l10n_latam_journal_id', string="Sequences")
    # TODO unify with l10n_ar_sequence_ids?. This one will not be needed in next version

    l10n_uy_share_sequences = fields.Boolean(
        'Unified Book', help='Use same sequence for all the documents in this journal')
    # TODO unify with l10n_ar_share_sequences?

    @api.onchange('l10n_uy_type')
    def onchange_journal_uy_type(self):
        """ If the uy type is contingency or preprintedthen use the unified sequence for all the documents """
        self.l10n_uy_share_sequences = bool(self.company_id.country_id.code == 'UY' and self.l10n_uy_type in ['preprinted', 'contingency'])

    def _l10n_uy_get_journal_codes(self):
        # TODO simil to l10n_ar method _get_journal_codes(). review if we can merge it somehow
        self.ensure_one()
        if self.type not in ['sale', 'purchase']:
            return []

        internal_types = ['invoice', 'debit_note', 'credit_note']
        document_types = self.env['l10n_latam.document.type'].search([
            ('internal_type', 'in', internal_types), ('country_id', '=', self.env.ref('base.uy').id)])

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

        return document_types.mapped('code')

    @api.model
    def create(self, values):
        """ Create Document sequences after create the journal """
        # TODO this will be removed in the next version
        res = super().create(values)
        if res.company_id.country_id.code == 'UY':
            res._l10n_uy_create_document_sequences()
        return res

    def write(self, values):
        """ Update Document sequences after update journal """
        to_check = set(['type', 'l10n_uy_type', 'l10n_uy_share_sequences', 'l10n_latam_use_documents'])
        res = super().write(values)
        if to_check.intersection(set(values.keys())):
            for rec in self:
                rec._l10n_uy_create_document_sequences()
        return res

    def _l10n_uy_create_document_sequences(self):
        """ IF DGI Configuration change try to review if this can be done and then create / update the document
        sequences """
        self.ensure_one()
        if self.company_id.country_id.code != 'UY':
            return True
        if not self.type == 'sale' or not self.l10n_latam_use_documents:
            return False

        sequences = self.l10n_uy_sequence_ids
        sequences.unlink()

        # Create Sequences
        internal_types = ['invoice', 'debit_note', 'credit_note']
        domain = [('country_id.code', '=', 'UY'), ('internal_type', 'in', internal_types)]
        codes = self._l10n_uy_get_journal_codes()
        if codes:
            domain.append(('code', 'in', codes))
        documents = self.env['l10n_latam.document.type'].search(domain)
        for document in documents:
            if self.l10n_uy_share_sequences and self.l10n_uy_sequence_ids:
                continue

            sequences |= self.env['ir.sequence'].create(document._get_document_sequence_vals(self))
        return sequences
