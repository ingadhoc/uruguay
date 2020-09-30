from odoo import models, fields


class L10nLatamIdentificationType(models.Model):

    _inherit = "l10n_latam.identification.type"

    l10n_uy_dgi_code = fields.Integer('DGI Code')
    # TODO improve. This one is Integer but in AR is Char. review new version type of fields what to use
