from odoo import api, models


class AccountCashRounding(models.Model):
    _inherit = "account.cash.rounding"

    @api.onchange("strategy")
    def _onchange_l10n_uy_ux_strategy(self):
        # Only a warning: the strategy can still be used with manual (non electronic) journals.
        if self.strategy == "biggest_tax" and self.env.company.country_code == "UY":
            return {
                "warning": {
                    "title": self.env._("Not supported in electronic invoicing"),
                    "message": self.env._(
                        "Uruguayan electronic invoices (CFE) do not support the 'Modify tax amount' strategy: "
                        "the rounding must be reported as a non billable item. Use 'Add a rounding line' "
                        "for electronic journals. You can keep this strategy for manual invoices."
                    ),
                }
            }
