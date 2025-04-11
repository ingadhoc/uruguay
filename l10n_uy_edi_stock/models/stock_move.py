from odoo import models, fields


class StockMove(models.Model):
    _inherit = "stock.move"

    l10n_uy_edi_addenda_ids = fields.Many2many(
        "l10n_uy_edi.addenda",
        string="Mandatory Disclosures",
        domain="[('type', '=', 'item'), ('apply_on', 'in', ['all', 'stock.picking'])]",
        ondelete="restrict",
    )
