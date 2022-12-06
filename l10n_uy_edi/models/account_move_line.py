from odoo import fields, models


class AccountMoveTax(models.Model):

    _inherit = 'account.move.line'

    resguardo_id = fields.Many2one('l10n.uy.resguardo')
