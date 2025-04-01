from odoo import _, api, models, fields
from odoo.exceptions import UserError


class L10nUyEdiDocument(models.Model):

    _inherit = 'l10n_uy_edi.document'

    picking_id = fields.Many2one("stock.picking", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'picking_id' in vals:
                vals.update({'res_model': 'stock.picking', 'res_id': vals.get('picking_id')})
        return super().create(vals_list)

    def _get_source_model_field(self, res_model=None):
        # EXTEND from l10n_uy_ux
        if res_model == "stock.picking":
            return "picking_id"
        return super()._get_source_model_field(res_model)

    def _get_uuid(self, record):
        # EXTEND from l10n_uy_edi
        """ uuid to identify picking (shortcut for testing env unicity) """
        if record._name != 'stock.picking':
            return super()._get_uuid(record)
        record.ensure_one()
        res = record._name + '-' + str(record.id)
        if record.company_id.l10n_uy_edi_ucfe_env == 'testing':
            res = 'sp' + str(record.id) + '-' + record.env.cr.dbname
        return res[:50]

    def _get_cfe_tag(self, res):
        # EXTEND from l10n_uy_edi
        if res._name != 'stock.picking':
            return super()._get_cfe_tag(res)

        res.ensure_one()
        tags = {'181': 'eRem', '124': 'eRem_Exp'}
        res = tags.get(res.l10n_latam_document_type_id.code)
        if not res:
            return UserError(_('Need to define the origin record of this EDI document'))
        return res

    def action_update_dgi_state(self):
        edi_pickings = self.filtered(lambda x: x.res_model == 'stock.picking')
        for edi_doc in edi_pickings:
            result = edi_doc._ucfe_inbox("360", {"Uuid": edi_doc.uuid})
            edi_doc._update_cfe_state(result)
        return super(L10nUyEdiDocument, self - edi_pickings).action_update_dgi_state()

    # Solo para Remito Exportacion
    # def _is_uy_remito_exp(self):
    #     return self.l10n_latam_document_type_id.code == '124'
