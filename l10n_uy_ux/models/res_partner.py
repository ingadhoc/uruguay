from odoo import models
from odoo.addons.l10n_uy_edi.models.res_partner import UY_RUT_DGI_CODE
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        # The update from DGI must not erase the data DGI does not inform
        if self.env.context.get("l10n_uy_ux_keep_values"):
            vals = {key: value for key, value in vals.items() if value is not False}
            self = self.with_context(l10n_uy_ux_keep_values=False)
        return super().write(vals)

    def action_l10n_uy_is_electronic_issuer(self):
        """Return True/False if the partner is an electronic issuer or not
        630 - Consulta si un RUT es emisor electronico"""
        self.ensure_one()
        # TODO KZ need to ensure that use the proper company
        edi_doc = self.env["l10n_uy_edi.document"]
        if self._l10n_uy_edi_get_dgi_code() == UY_RUT_DGI_CODE:
            result = edi_doc._ucfe_inbox("630", {"RutEmisor": self.vat})

            cod_rta = False
            response = result.get("response")
            if response is not None:
                cod_rta = response.findtext(".//{*}CodRta")

            if cod_rta == "00":
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "type": "info",
                        "message": self.env._("It is an electronic issuer"),
                        "next": {"type": "ir.actions.act_window_close"},
                    },
                }
            elif cod_rta == "01":
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "type": "danger",
                        "message": self.env._("It is NOT an electronic issuer"),
                        "next": {"type": "ir.actions.act_window_close"},
                    },
                }
        else:
            raise UserError(self.env._("You can only check if the partner has a RUT identification type"))

    def l10n_uy_ux_update_from_dgi(self):
        """Update the partners with RUT using the DGI query of l10n_uy_edi, keeping the data DGI does not inform"""
        partners = self.filtered(lambda p: p.vat and p._l10n_uy_edi_get_dgi_code() == UY_RUT_DGI_CODE)
        if not partners:
            raise UserError(self.env._("No partner with RUT was found to update"))
        for partner in partners.with_context(l10n_uy_ux_keep_values=True):
            partner.button_l10n_uy_populate_from_vat()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._("%s partners updated from DGI", len(partners)),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def l10n_uy_ux_update_all_from_dgi(self):
        """Update from DGI every partner with RUT"""
        return self.search([("vat", "!=", False)]).l10n_uy_ux_update_from_dgi()
