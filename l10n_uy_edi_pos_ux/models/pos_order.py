from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_uy_edi_cfe_state = fields.Selection(related="account_move.l10n_uy_edi_cfe_state")
    l10n_uy_edi_error = fields.Text(related="account_move.l10n_uy_edi_error")

    def _generate_pos_order_invoice(self):
        return super(PosOrder, self.with_context(l10n_uy_edi_pos_sale=True))._generate_pos_order_invoice()
