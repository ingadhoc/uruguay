import pprint

from odoo import api, fields, models
from odoo.addons.server_mode.mode import get_mode
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_uy_dgi_crt_id = fields.Many2one(related="company_id.l10n_uy_dgi_crt_id", readonly=False)
    l10n_uy_report_params = fields.Char(related="company_id.l10n_uy_report_params", readonly=False)
    l10n_uy_edi_is_prod_db = fields.Boolean(
        default=lambda self: not get_mode(),
        help="Technical field. True when running on a real production database (server_mode not set)."
        " Used to hide the UCFE environment selector, since on production the environment is always"
        " 'production'.",
    )

    @api.onchange("l10n_uy_edi_ucfe_env")
    def uy_ux_onchange_ufce_env(self):
        """Update UCFE param with what we have when Environment change."""

        if self.l10n_uy_edi_ucfe_env == "production":
            config = self.company_id.l10n_uy_edi_ucfe_prod_env
        elif self.l10n_uy_edi_ucfe_env == "testing":
            config = self.company_id.l10n_uy_edi_ucfe_test_env
        elif self.l10n_uy_edi_ucfe_env == "demo":
            config = "{}"
        else:
            config = False

        config = safe_eval(config or "{}")
        uruware_fields = [
            "l10n_uy_edi_ucfe_password",
            "l10n_uy_edi_ucfe_commerce_code",
            "l10n_uy_edi_ucfe_terminal_code",
        ]
        for ufce_field in uruware_fields:
            self[ufce_field] = config.get(ufce_field, "")

    def set_values(self):
        super().set_values()
        self.uy_ux_update_saved_param_data()

    def uy_ux_update_saved_param_data(self):
        """If any of the ucfe params change then update the env_data values of the current selected environment"""
        env_data = {
            "l10n_uy_edi_ucfe_password": self.l10n_uy_edi_ucfe_password or "",
            "l10n_uy_edi_ucfe_commerce_code": self.l10n_uy_edi_ucfe_commerce_code or "",
            "l10n_uy_edi_ucfe_terminal_code": self.l10n_uy_edi_ucfe_terminal_code or "",
        }

        if self.l10n_uy_edi_ucfe_env == "production":
            env_data.update({"l10n_uy_edi_ucfe_prod_env": pprint.pformat(env_data)})
        elif self.l10n_uy_edi_ucfe_env == "testing":
            env_data.update({"l10n_uy_edi_ucfe_test_env": pprint.pformat(env_data)})

        self.company_id.write(env_data)

    @api.onchange("l10n_uy_report_params")
    def uy_ux_onchange_l10n_uy_report_params(self):
        """Corroboramos que los valores ingresados sean válidos."""
        if not self.l10n_uy_report_params:
            return

        if len(safe_eval(self.l10n_uy_report_params or "[]")) < 2:
            raise UserError(
                self.env._(
                    "The field must contain at least two values: parameter name and value. "
                    "Please verify that the values were entered in the correct format."
                )
            )

        param_names = safe_eval(self.l10n_uy_report_params or "[]")[0]
        valid_params = ["adenda", "reporte", "formato"]
        invalid_params = [param for param in param_names if param not in valid_params]
        if invalid_params:
            raise UserError(
                self.env._(
                    "The following entered parameters are invalid: %(params)s. Allowed values are: %(allowed)s.",
                    params=", ".join(invalid_params),
                    allowed=", ".join(valid_params),
                )
            )
        reporte_values = [i for i, name in enumerate(param_names) if name == "reporte"]
        if len(reporte_values) > 1:
            raise UserError(
                self.env._(
                    "The 'reporte' parameter contains two different values. "
                    "Only one custom value per 'reporte' parameter is allowed. "
                    "Please check your report configuration."
                )
            )
