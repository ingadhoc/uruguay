##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class AccountJournal(models.Model):

    _inherit = "account.journal"

    l10n_uy_type = fields.Selection(
        [('manual', 'Manual'),
         ('preprinted', 'Preprinted (Traditional)'),
         ('electronic', 'Electronic'),
         ('contingency', 'Contingency')],
        string='Invoicing Type', copy=False, default="manual",
        help="Type of journals that can be used for Uruguayan companies:\n"
        "* Manual: You can generate any document type (electronic or traditional) entering the"
        " document number manually. This is usefull if you have electronic documents created using"
        " external systems and then you want to upload the documents to Odoo. Similar to Argentinean"
        " Online Invoice type.\n"
        "* Preprinted: For traditional invoicing using a pre printed tradicional documents (the ones with code 0).\n"
        "* Electronic: To generate electronic documents via web service to DGI using UCFE Uruware provider service.\n"
        "* Contingency: To generate documents to be send post morten via web service"
        " (when electronic is not working).\n")


    l10n_uy_sequence_ids = fields.One2many('ir.sequence', 'l10n_latam_journal_id', string="Sequences")
    # TODO unify with l10n_ar_sequence_ids?. This one will not be needed in next version

    l10n_uy_share_sequences = fields.Boolean(
        'Unified Book', help='Use same sequence for all the documents in this journal')
    # TODO unify with l10n_ar_share_sequences?

    @api.onchange('l10n_uy_type')
    def onchange_journal_uy_type(self):
        """ If the uy type is contingency or preprintedthen use the unified sequence for all the documents """
        self.l10n_uy_share_sequences = bool(
            self.company_id.country_id.code == 'UY' and self.l10n_uy_type in ['preprinted', 'contingency'])

    # TODO similar to _get_journal_codes() in l10n_ar, see if we can merge it in a future
    def _l10n_uy_get_journal_codes(self):
        """ return list of the available document type codes for uruguayan sales journals"""
        self.ensure_one()
        if self.type != 'sale':
            return []

        if self.l10n_uy_type == 'preprinted':
            available_types = ['0']
        elif self.l10n_uy_type == 'electronic':
            available_types = ['101', '102', '103', '111', '112', '113', '121', '122', '123']
        elif self.l10n_uy_type == 'contingency':
            available_types = ['201', '211', '212', '213', '221', '222', '223']
        elif self.l10n_uy_type == 'manual':
            internal_types = ['invoice', 'debit_note', 'credit_note']
            doc_types = self.env['l10n_latam.document.type'].search([
                ('internal_type', 'in', internal_types),
                ('country_id', '=', self.env.ref('base.uy').id)])
            available_types = doc_types.mapped('code')

        return available_types

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

    # TODO KZ simil to _l10n_ar_create_document_sequences, since to merge this two methods in the future
    def _l10n_uy_create_document_sequences(self):
        """ IF DGI configuration change try to review if this can be done and then create / update the document
        sequences """
        self.ensure_one()
        if self.company_id.country_id.code != 'UY':
            return True
        # Si no soy de tipo venta, no uso documentos o soy de tipo electronico/manual no genero secuencias.
        # * en diarios electronicos la secuencias se asignan al validar la factura durecto desde Uruware.
        # * en diarios manuales los usuarios no tienen secuencia y deben agregar el numero de documento de manera manual siempre
        if not self.type == 'sale' or not self.l10n_latam_use_documents or self.l10n_uy_type in ['electronic', 'manual']:
            return False

        sequences = self.l10n_uy_sequence_ids
        sequences.unlink()

        # Create Sequences
        # TODO KZ improve maybe skip this and use _get_l10n_latam_documents_domain direclty?
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
