from odoo import fields, models, api
from odoo.osv import expression


class L10nLatamDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    def _get_move_type(self, journal_type="purchase"):
        """ This method should be moved to latam module in future versions, will be available in 18, is a temporal method here. It is necessary to get the move_type depending on the internal type of the invoice document type. See https://github.com/odoo/odoo/pull/140198 """
        self.ensure_one()
        prefix = "in" if journal_type == "purchase" else "out"
        data = {
            'invoice': prefix + '_invoice',
            'debit_note':  prefix + '_invoice',
            'credit_note':  prefix + '_refund',
        }
        return data.get(self.internal_type)
