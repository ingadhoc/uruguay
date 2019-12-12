from odoo import models, fields


class ResPartnerIdCategory(models.Model):

    _inherit = "res.partner.id_category"

    l10n_uy_dgi_code = fields.Integer('DGI Code')

    # TODO delete this when we remove the relation to l10n_ar_partner
    afip_code = fields.Integer(required=False)
