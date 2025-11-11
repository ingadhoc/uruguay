import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartnerUpdateFromPadronUyField(models.TransientModel):
    """Uruguay-specific field model for DGI updates"""

    _inherit = "res.partner.update.from.padron.field"


class ResPartnerUpdateFromPadronUyWizard(models.TransientModel):
    """Uruguay-specific wizard for DGI partner updates"""

    _inherit = "res.partner.update.from.padron.wizard"

    def get_partner_data(self, partner):
        """Implementación específica para DGI Uruguay"""
        return partner.action_l10n_uy_get_data_from_dgi()

    @api.model
    def default_get(self, fields):
        country_code = self.env["res.partner"].browse(self._context.get("active_ids")).country_id.code
        if country_code == "UY":
            res = super().default_get(fields)
            context = self.env.context
            if context.get("active_model") == "res.partner" and context.get("active_ids"):
                partners = self.get_partners()
                if not partners:
                    raise UserError(self.env._("No partner with RUT was found to update"))
                elif len(partners) == 1:
                    res["state"] = "selection"
                    res["partner_id"] = partners[0].id
            return res
        return super().default_get(fields)

    @api.model
    def get_partners(self):
        """Busca partners con RUT válido para Uruguay"""
        domain = [("vat", "!=", False), ("l10n_latam_identification_type_id.l10n_uy_dgi_code", "=", "2")]
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            # Filtrar partners que pertenecen a compañías uruguayas
            uy_partners = (
                self.env["res.partner"].browse(active_ids).filtered(lambda p: p.company_id.country_id.code == "UY")
            )
            active_ids = uy_partners.ids
            if active_ids:
                domain.append(("id", "in", active_ids))
        return self.env["res.partner"].search(domain)

    @api.model
    def _get_domain(self):
        """Define campos específicos de Uruguay/DGI"""
        fields_names = [
            "name",
            "street",
            "street2",
            "city",
            "zip",
            "state_id",
            "country_id",
            "comment",
            "phone",
            "mobile",
            "email",
            "ref",
        ]
        return [("model", "=", "res.partner"), ("name", "in", fields_names)]

    def _get_many2one_fields(self):
        """Campos Many2one específicos de Uruguay"""
        return ["state_id", "country_id"]

    def _get_many2many_fields(self):
        """Campos Many2many específicos de Uruguay"""
        return []

    def _get_error_message(self, error):
        """Mensaje de error personalizado para DGI"""
        return f"Falló actualización DGI: {error}"

    # Override partner_ids to use Uruguay-specific relation table
    partner_ids = fields.Many2many(
        "res.partner",
        "partner_update_from_padron_uy_rel",
        "update_id",
        "partner_id",
        string="Partners",
        default=lambda self: self.get_partners(),
    )
