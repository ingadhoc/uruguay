# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nLatamDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    def _get_document_sequence_vals(self, journal):
        self.ensure_one()
        values = super()._get_document_sequence_vals(journal)
        if self.country_id.code != 'UY':
            return values
        values.update({'padding': 7, 'prefix': '', 'l10n_latam_document_type_id': self.id,
                       'l10n_latam_journal_id': journal.id, 'name': '%s - %s' % (journal.name, self.display_name)})
        return values
