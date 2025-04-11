from freezegun import freeze_time
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.exceptions import UserError
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.addons.stock.tests.common import TestStockCommon


@tagged("-at_install", "post_install", "post_install_l10n", "mock")
class TestMock(TestUyEdi, TestStockCommon):

    @classmethod
    def setUpClass(cls, chart_template_ref="uy"):
        super().setUpClass(chart_template_ref=chart_template_ref)

    def _create_picking(self, **kwargs):
        with freeze_time(self.frozen_today, tz_offset=3):
            picking = self.PickingObj.create({
                "partner_id": self.partner_local_tk.id,
                "picking_type_id": self.picking_type_out,
                "location_id": self.stock_location,
                "location_dest_id": self.customer_location,
                "state": "draft",
                **kwargs,
            })
            # product_vat_22
            self.MoveObj.create({
                "name": self.productA.name,
                "product_id": self.productA.id,
                "product_uom_qty": 10,
                "product_uom": self.productA.uom_id.id,
                "picking_id": picking.id,
                "location_id": self.stock_location,
                "location_dest_id": self.customer_location})
        return picking

    def _mock_send_delivery_guide(self, picking, expected_xml_file, get_pdf=None, exception=None):
        inbox_patch = dict(
            target=f"{self.utils_path}._ucfe_inbox",
            return_value=self._mocked_response(expected_xml_file, exception=exception),
        )
        query_patch = dict(
            target=f"{self.utils_path}._ucfe_query",
            return_value=self._mocked_response(expected_xml_file + "_pdf" if get_pdf else False),
        )
        with patch(**inbox_patch), patch(**query_patch):
            self._send_and_print(picking)

    def test_10_delivery_guide_accepted_and_pdf(self):
        """ process an accepted picking and generate the legal pdf """
        picking = self._create_picking()
        picking.action_confirm()
        self._mock_send_delivery_guide(picking, "mock_10_delivery_guide_accepted", get_pdf=True)

        self.assertEqual(picking.l10n_uy_edi_cfe_state, "accepted")
        self.assertTrue(picking.edi_pdf_report_file, "The pdf file was not created.")

    def test_20_delivery_guide_pdf_check_status(self):
        picking = self._create_picking()
        picking.action_confirm()
        self._mock_send_delivery_guide(picking, "mock_20_delivery_guide_received", get_pdf=True)

        self.assertEqual(picking.l10n_uy_edi_cfe_state, "received")
        self.assertTrue(picking.edi_pdf_report_file, "The pdf file was not created.")

        self._mock_update_dgi_state(picking, "mock_20_delivery_guide_status")
        self.assertEqual(picking.l10n_uy_edi_cfe_state, "accepted")

    def test_30_delivery_guide_rejected(self):
        """ simulate we have a picking in state received. then check status from uruware and receive
        rejected state """
        picking = self._create_picking()
        picking.action_confirm()
        self._mock_send_delivery_guide(picking, "mock_30_delivery_guide_rejected", get_pdf=True)

        self.assertEqual(picking.l10n_uy_edi_cfe_state, "received")
        self.assertTrue(picking.edi_pdf_report_file, "The pdf file was not created.")

        self._mock_update_dgi_state(picking, "mock_delivery_guide_rejected")
        self.assertEqual(picking.l10n_uy_edi_cfe_state, "rejected")

    def test_40_delivery_guide_error(self):
        """ capture error return by DGI because the data we send in the XML is not valid """
        partner_local_with_error = self.env["res.partner"].create({
            "name": "IEB Internacional",
            "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_dni").id,
            "vat": "218435730016",
            "street": "Bach 0",
            "city": "Aeroparque",
            "state_id": self.env.ref("base.state_uy_02").id,
            "country_id": self.env.ref("base.uy").id,
            "email": "rut@example.com",
        })
        picking = self._create_picking(partner_id=partner_local_with_error.id)
        picking.action_confirm()
        error_msg = ".*por lo que se espera país AR, BR, CL ó PY, pero se recibió UY.*"
        with self.assertRaisesRegex(UserError, error_msg):
            self._mock_send_delivery_guide(picking, "mock_40_delivery_guide_error")

        self.assertFalse(picking.edi_pdf_report_file, "Since we have an error the pdf file must not exist.")
        self.assertEqual(picking.l10n_uy_edi_cfe_state, "error")
        self.assertRegex(picking.l10n_uy_edi_error, error_msg)
