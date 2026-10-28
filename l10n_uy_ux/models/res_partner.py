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
        # Contacts of a company take its RUT: DGI data is for the company, not for them
        partners = self.filtered(
            lambda p: p == p.commercial_partner_id and p.vat and p._l10n_uy_edi_get_dgi_code() == UY_RUT_DGI_CODE
        )
        if not partners:
            raise UserError(self.env._("No partner with RUT was found to update"))
        not_updated = self.env["res.partner"]
        for partner in partners.with_context(l10n_uy_ux_keep_values=True):
            # l10n_uy_edi returns False when it does not update the partner (no UY country, RUT not found in DGI)
            if partner.button_l10n_uy_populate_from_vat() is False:
                not_updated |= partner
        message = self.env._("%s partners updated from DGI", len(partners - not_updated))
        if not_updated:
            message += "\n" + self.env._(
                "Not updated (no data in DGI or country is not Uruguay): %s",
                ", ".join(not_updated.mapped("display_name")),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if not_updated else "success",
                "message": message,
                "sticky": bool(not_updated),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def l10n_uy_ux_update_all_from_dgi(self):
        """Update from DGI every partner with RUT"""
        return self.search([("vat", "!=", False)]).l10n_uy_ux_update_from_dgi()
