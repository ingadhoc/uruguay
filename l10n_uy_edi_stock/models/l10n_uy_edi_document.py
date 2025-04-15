from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nUyEdiDocument(models.Model):
    _inherit = "l10n_uy_edi.document"

    picking_id = fields.Many2one("stock.picking", readonly=True)

    def _get_origin_record(self):
        self.ensure_one()
        return self.picking_id or super()._get_origin_record()

    def _get_uuid(self, origin_record):
        # EXTEND from l10n_uy_edi
        """uuid to identify picking (shortcut for testing env unicity)"""
        if origin_record._name != "stock.picking":
            return super()._get_uuid(origin_record)
        origin_record.ensure_one()
        res = origin_record._name + "-" + str(origin_record.id)
        if origin_record.company_id.l10n_uy_edi_ucfe_env == "testing":
            res = "sp" + str(origin_record.id) + "-" + origin_record.env.cr.dbname
        return res[:50]

    def _get_cfe_tag(self, origin_record):
        # EXTEND from l10n_uy_edi
        if origin_record._name != "stock.picking":
            return super()._get_cfe_tag(origin_record)

        origin_record.ensure_one()
        tags = {"181": "eRem", "124": "eRem_Exp"}
        origin_record = tags.get(origin_record.l10n_latam_document_type_id.code)
        if not origin_record:
            return UserError(_("Need to define the origin record of this EDI document"))
        return origin_record

    def action_update_dgi_state(self):
        edi_pickings = self.filtered(lambda x: x.picking_id)
        for edi_doc in edi_pickings:
            result = edi_doc._ucfe_inbox("360", {"Uuid": edi_doc.uuid})
            edi_doc._update_cfe_state(result)
        return super(L10nUyEdiDocument, self - edi_pickings).action_update_dgi_state()

    # Solo para Remito Exportacion
    # def _is_uy_remito_exp(self):
    #     return self.l10n_latam_document_type_id.code == '124'
