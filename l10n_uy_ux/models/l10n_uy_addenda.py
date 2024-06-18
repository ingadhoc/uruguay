from odoo import models, fields


class L10nUyAddenda(models.Model):

    _inherit = "l10n.uy.addenda"
    _order = "sequence asc, id"

    sequence = fields.Integer()
    active = fields.Boolean(default=True)
    condition = fields.Char(default="False")

    apply_on = fields.Selection(
        [
            ('account.move', 'Invoices and Tickets'),
            ('account.move.line', 'Resguardos')
        ],
        required=True, default='account.move'
    )
