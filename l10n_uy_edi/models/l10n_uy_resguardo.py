from odoo import fields, models


class L10nUyResguardo(models.Model):

    _name = 'l10n.uy.resguardo'
    _inherit = ['l10n.uy.cfe']
    _description = 'Resguardos (UY)'

    name = fields.Char()
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Document Type', copy=False)
    l10n_latam_document_number = fields.Char(string='Document Number', readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    aml_id = fields.One2many('account.move.line', 'resguardo_id')
    date = fields.Date()
    partner_id = fields.Many2one('res.partner', compute="compute_aml_vals")
    currency_id = fields.Many2one('res.currency', compute="compute_aml_vals")

    def compute_aml_vals(self):
        for rec in self:
            rec.partner_id = False
            rec.currency_id = False

    def name_get(self):
        """ Display: 'Document Type Prefix : Document number' if not / """
        res = []
        for rec in self:
            if rec.l10n_latam_document_number:
                name = "(%s %s)" % (rec.l10n_latam_document_type_id.doc_code_prefix, rec.l10n_latam_document_number)
            else:
                name = '/'
            res.append((rec.id, name))
        return res
