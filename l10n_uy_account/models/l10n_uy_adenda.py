from odoo import models, fields


class L10nUyAdenda(models.Model):

    _name = "l10n.uy.adenda"
    _description = "CFE Adenda"
    _order = "sequence asc, id"

    sequence = fields.Integer()
    name = fields.Char()
    active = fields.Boolean(default=True)
    content = fields.Text()
    condition = fields.Char(default="True")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    apply_on = fields.Selection([
        ('account.move', 'Facturas y Tickets'),
        ('stock.picking', 'Remitos'),
        ('account.move.line', 'Resguardos'),
        ('all', 'Todos los CFE'),
    ], required=True)
