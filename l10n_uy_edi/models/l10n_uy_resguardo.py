from odoo import fields, models


class L10nUyResguardo(models.AbstractModel):

    _name = 'l10n.uy.resguardo'
    _inherit = ['l10n.uy.cfe']
    _description = 'Resguardos (UY)'

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    aml_id = fields.One2many('account.move.line', 'resguardo_id')
    date = fields.Date()
    partner_id = fields.Many2one('res.partner', compute="compute_aml_vals")
    currency_id = fields.Many2one('res.currency', compute="compute_aml_vals")

    def compute_aml_vals(self):
        for rec in self:
            rec.partner_id = False
            rec.currency_id = False
