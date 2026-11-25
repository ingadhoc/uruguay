from odoo import api, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    l10n_uy_contingency_reason = fields.Text(readonly=True)

    def _l10n_uy_pos_enter_contingency(self, reason):
        for session in self.filtered(lambda s: not s.invoice_contingency):
            session.write({"invoice_contingency": True, "l10n_uy_contingency_reason": reason})
            session.message_post(body=self.env._("Contingency mode activated automatically: %s", reason))

    def action_unset_invoice_contingency(self):
        self.l10n_uy_contingency_reason = False
        return super().action_unset_invoice_contingency()

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ["l10n_uy_contingency_reason"]
