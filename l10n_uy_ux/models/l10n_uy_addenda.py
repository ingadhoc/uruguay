from odoo import models, fields


class L10nUyAddenda(models.Model):
    _inherit = "l10n_uy_edi.addenda"
    _order = "sequence asc, id"

    sequence = fields.Integer()
    active = fields.Boolean(default=True)
    condition = fields.Char(default="False")
    apply_on = fields.Selection([
        ("all", "All CFE"),
        ("account.move", "Invoices and Tickets"),
        ], required=True, default="account.move",
    )
