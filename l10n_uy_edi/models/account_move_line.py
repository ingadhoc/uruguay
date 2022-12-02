from odoo import fields, models


class AccountMoveTax(models.Model):

    _inherit = 'account.move.line'

    resguardo_id = fields.Char('Nro Resguardo')
    # TODO KZ en realidad no seria un _id, queremos un modelo aparte? para poder revisar todos los cfe?
