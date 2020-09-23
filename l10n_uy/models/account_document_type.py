from odoo import models


class AccountDocmentType(models.Model):

    _inherit = 'account.document.type'

    def get_document_sequence_vals(self, journal):
        vals = super().get_document_sequence_vals(journal)
        if self.localization == 'uruguay':
            vals.update({
                'padding': 7,
                'prefix': self.doc_code_prefix,
            })
        return vals
