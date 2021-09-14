# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, api
from odoo.osv import expression


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

    # TODO this has been already implemented in 14.0 in latam remove this method when migrating
    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if operator == 'ilike' and not (name or '').strip():
            domain = []
        else:
            domain = ['|', ('name', 'ilike', name), ('code', 'ilike', name)]
        ids = self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return self.browse(ids).name_get()
