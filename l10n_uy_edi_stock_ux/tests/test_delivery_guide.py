from odoo import Command
from odoo.addons.l10n_uy_edi_stock.tests.common import TestUyEdiStock
from odoo.tests.common import tagged


@tagged("-at_install", "post_install", "post_install_l10n", "l10n_uy_ux")
class TestDeliveryGuideUx(TestUyEdiStock):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mocked_cfes_path = "l10n_uy_edi_stock_ux/tests/expected_cfes/"

    def test_15_delivery_guide_product_codes(self):
        # TODO 20.0: remove, it is native in Odoo from 20.0 (odoo/enterprise master, https://github.com/odoo/enterprise/pull/129215)
        """La referencia interna y el código de barras se informan en sus propios nodos <CodItem> y NomItem no
        incluye el prefijo de la referencia interna"""
        product = self.env["product.product"].create(
            {
                "name": "Coded delivery product",
                "default_code": "CODE123",
                "barcode": "7730912350032",
            }
        )
        picking = self._create_stock_picking(
            move_ids=[
                Command.create(
                    {
                        "product_id": product.id,
                        "product_uom_qty": 1.0,
                        "product_uom": product.uom_id.id,
                        "location_id": self.stock_location.id,
                        "location_dest_id": self.customer_location.id,
                    }
                )
            ]
        )
        self._validate_and_create_delivery_guide(picking)
        self._check_cfe(picking, "15_delivery_guide_product_codes")
