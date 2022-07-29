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

    """ TODO KZ
    Ver si esto suma en otro lado

    internal_types = ['invoice', 'debit_note', 'credit_note']
    document_types = self.env['l10n_latam.document.type'].search(
        [('internal_type', 'in', internal_types), ('country_id.code', '=', 'UY')])

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
    """

    """ TODO KZ add this in the place where we use the valid code sequences
    # Si no soy de tipo venta, no uso documentos o soy de tipo electronico/manual no genero secuencias.
    # * en diarios electronicos la secuencias se asignan al validar la factura durecto desde Uruware.
    # * en diarios manuales los usuarios no tienen secuencia y deben agregar el numero de documento de manera manual siempre
    if not self.type == 'sale' or not self.l10n_latam_use_documents or self.l10n_uy_type in ['electronic', 'manual']:
        return False

    codes = self._l10n_uy_get_journal_codes()
    if codes:
        domain.append(('code', 'in', codes))
    documents = self.env['l10n_latam.document.type'].search(domain)
    """
