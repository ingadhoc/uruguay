from odoo import api, fields, models


class L10nUyTaxType(models.Model):

    _name = 'l10n.uy.tax.type'
    _description = "Uruguay EDI Tax Type"

    form = fields.Char()
    code = fields.Char()
    name = fields.Char()
    description = fields.Char()
    retention = fields.Boolean()

    def name_get(self):
        """ Display: 'Form-Code Name """
        res = []
        for rec in self:
            name = "%s-%s %s" % (rec.form, rec.code, rec.name)
            res.append((rec.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = [
            '|', '|', ('code', operator, name),
            ('form', operator, name), ('name', operator, name)]
        rec = self.search(domain + args, limit=limit)
        return rec.name_get()
