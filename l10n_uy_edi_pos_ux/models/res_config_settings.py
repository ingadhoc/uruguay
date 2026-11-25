from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_l10n_uy_cfe_error_flow = fields.Selection(related="pos_config_id.l10n_uy_cfe_error_flow", readonly=False)
    pos_l10n_uy_allow_close_with_cfe_error = fields.Boolean(
        related="pos_config_id.l10n_uy_allow_close_with_cfe_error", readonly=False
    )
    pos_l10n_uy_check_final_consumer_limit = fields.Boolean(
        related="pos_config_id.l10n_uy_check_final_consumer_limit", readonly=False
    )
    pos_l10n_uy_simulate_cfe_error = fields.Boolean(related="pos_config_id.l10n_uy_simulate_cfe_error", readonly=False)
