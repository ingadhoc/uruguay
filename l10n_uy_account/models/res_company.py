from odoo import models, fields


class ResCompany(models.Model):

    _inherit = 'res.company'

    l10n_uy_dgi_house_code = fields.Integer(
        "DGI House Code", default=1, help="This value is used when the CFE xml is sent (Field 47: Emisor/CdgDGISucur)")
    l10n_uy_adenda_ids = fields.One2many('l10n.uy.adenda', 'company_id', 'CFE Adendas')

    def _localization_use_documents(self):
        """ Uruguayan localization use documents """
        self.ensure_one()
        return True if self.country_id.code == 'UY' else super()._localization_use_documents()
