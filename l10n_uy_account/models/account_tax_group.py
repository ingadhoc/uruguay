from odoo import api, fields, models


class AccountTaxGroup(models.Model):

    _inherit = 'account.tax.group'

    l10n_uy_form = fields.Char()
    l10n_uy_code = fields.Char()
    l10n_uy_imprubro = fields.Char()
    l10n_uy_description = fields.Char()
    l10n_uy_retention = fields.Boolean()

    # def name_get(self):
    #     """ Display: 'Form-Code Name """
    #     res = []
    #     for rec in self:
    #         name = "%s-%s %s" % (rec.l10n_uy_form, rec.l10n_uy_code, rec.name)
    #         res.append((rec.id, name))
    #     return res

    # @api.model
    # def name_search(self, name, args=None, operator='ilike', limit=100):
    #     args = args or []
    #     domain = [
    #         '|', '|', ('l10n_uy_code', operator, name),
    #         ('l10n_uy_form', operator, name), ('name', operator, name)]
    #     rec = self.search(domain + args, limit=limit)
    #     return rec.name_get()
