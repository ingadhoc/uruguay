from odoo import models, fields


class L10nUyAddenda(models.Model):

    _inherit = "l10n.uy.addenda.disclosure"

    apply_on = fields.Selection(selection_add=[('stock.picking', 'Delivery Guide')])
