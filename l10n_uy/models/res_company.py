##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api


class ResCompany(models.Model):

    _inherit = "res.company"

    # TODO delete this all this fields and methods when came to 13.0

    localization = fields.Selection(selection_add=[('uruguay', 'Uruguay')])

    @api.onchange('localization')
    def change_localization(self):
        if self.localization == 'uruguay' and not self.country_id:
            self.country_id = self.env.ref('base.uy')
