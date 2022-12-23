from odoo import fields, models


class L10nAccountDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    internal_type = fields.Selection(selection_add=[('stock_picking', 'Remito')])

    def _format_document_number(self, document_number):
        """ By the moment format document_number and return
        NOTE: In a future let us to Make validation of the given document number """
        self.ensure_one()
        if self.country_id.code != "UY":
            return super()._format_document_number(document_number)

        if not document_number:
            return False

        return document_number.zfill(8)
