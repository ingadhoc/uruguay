from odoo import fields, models


class L10nUyAddenda(models.Model):
    _inherit = "l10n_uy_edi.addenda"

    apply_on = fields.Selection(selection_add=[("stock.picking", "Delivery Guide")], default="all")
