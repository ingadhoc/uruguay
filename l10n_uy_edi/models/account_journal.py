# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    # TODO I think we should add a type for facturas de contigencia?
    l10n_uy_pos_type = fields.Selection(
        [('manual', 'Manual'), ('online', 'Online')], string='DGI Type of Document',
        help='You must select "Online" for journals with documents that need to be sent to DGI automatically.'
        ' In this case you must upload a CAF file for each type of document you will use in this journal.\n'
        'You must select "Manual" if you have already generated those documents using a different system in the past,'
        ' and you want to register them in Odoo now.', copy=False)

    # TODO Tenemos algo que se llama puntos de emision, ver si esto lo podemos configurar aca, seria como el AFIP Pos Number?
