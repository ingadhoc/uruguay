# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    l10n_uy_additional_info = fields.Text(
        "Info. adicional del item",
        help='Información adicional del item')
