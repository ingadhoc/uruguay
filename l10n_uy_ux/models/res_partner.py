from odoo import models
from odoo.addons.l10n_uy_edi.models.res_partner import UY_RUT_DGI_CODE
from odoo.exceptions import UserError

DGI_FIELDS = ("name", "ref", "street", "street2", "city", "zip", "state_id", "phone", "email")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def write(self, vals):
        # The update from DGI must not erase the data DGI does not inform: only on the partner being updated, and
        # only for the fields button_l10n_uy_populate_from_vat() writes
        if self.env.context.get("l10n_uy_ux_keep_values") and self.ids == [self.env.context["l10n_uy_ux_keep_values"]]:
            vals = {key: value for key, value in vals.items() if value is not False or key not in DGI_FIELDS}
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
            raise UserError(self.env._("Only a partner with a Uruguayan RUT can be checked in DGI"))

    def l10n_uy_ux_update_from_dgi(self):
        """Update the partners with RUT using the DGI query of l10n_uy_edi, keeping the data DGI does not inform"""
        # Contacts of a company take its RUT: DGI data is for the company, not for them
        partners = self.filtered(
            lambda p: p == p.commercial_partner_id and p.vat and p._l10n_uy_edi_get_dgi_code() == UY_RUT_DGI_CODE
        )
        if not partners:
            raise UserError(self.env._("No partner with RUT was found to update"))
        not_updated = self.env["res.partner"]
        errors = []
        for partner in partners:
            # An error of one partner (UCFE answered with errors) must not undo the ones already updated
            try:
                with self.env.cr.savepoint():
                    updated = partner.with_context(l10n_uy_ux_keep_values=partner.id).button_l10n_uy_populate_from_vat()
            except UserError as error:
                errors.append("%s: %s" % (partner.display_name, error))
                continue
            # l10n_uy_edi returns False when it does not update the partner (no UY country, RUT not found in DGI)
            if updated is False:
                not_updated |= partner
        message = self.env._("%s partners updated from DGI", len(partners) - len(not_updated) - len(errors))
        if not_updated:
            message += "\n" + self.env._(
                "Not updated (no data in DGI or country is not Uruguay): %s",
                ", ".join(not_updated.mapped("display_name")),
            )
        if errors:
            message += "\n" + self.env._("Not updated because of an error: %s", "\n".join(errors))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "warning" if not_updated or errors else "success",
                "message": message,
                "sticky": bool(not_updated or errors),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def l10n_uy_ux_update_all_from_dgi(self):
        """Update from DGI every Uruguayan company with RUT of the current company"""
        return self.search(
            [
                ("vat", "!=", False),
                ("is_company", "=", True),
                ("country_id.code", "=", "UY"),
                ("company_id", "in", [False, self.env.company.id]),
            ]
        ).l10n_uy_ux_update_from_dgi()
