from odoo import models
from odoo.tools.barcode import check_barcode_encoding


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _l10n_uy_edi_get_cod_items(self):
        """B2 TpoCod, B3 Cod ("TABLA de Códigos del Ítem", hasta 5 ocurrencias por ítem).

        Devuelve los códigos del producto a informar en el CFE para que el sistema receptor pueda identificar el
        ítem: la referencia interna (tipo INT1) y el código de barras (tipo GTIN13). El código de barras solo se
        informa si es un EAN-13 válido, ya que DGI valida el dígito verificador de los GTIN.

        Mismo nombre que el método propuesto a Odoo (odoo/enterprise master, l10n_uy_edi), así al migrar se elimina
        este método sin tocar a quienes lo llaman.
        """
        # TODO 20.0: remove, it is native in Odoo from 20.0 (odoo/enterprise master, https://github.com/odoo/enterprise/pull/129215)
        cod_items = []
        if not self:
            return cod_items
        self.ensure_one()
        if self.default_code:
            cod_items.append({"TpoCod": "INT1", "Cod": self.default_code[:35]})
        if self.barcode and check_barcode_encoding(self.barcode, "ean13"):
            cod_items.append({"TpoCod": "GTIN13", "Cod": self.barcode})
        return cod_items
