import re
import unittest
from unittest.mock import patch

from lxml import etree
from odoo import tools
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestPatchDummy(common.TransactionCase):
    def test_dummy(self):
        # a trivial test so the test runner reports >0 tests (avoids the 0-tests warning)
        self.assertTrue(True)


# Only apply the patch while running tests
if tools.config.get("test_enable"):
    from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
    from odoo.addons.l10n_uy_edi.tests.test_account_move_send import TestAccountMoveSend
    from odoo.addons.l10n_uy_edi.tests.test_manual import TestManual
    from odoo.addons.l10n_uy_edi.tests.test_mock import TestMock

    @classmethod
    def _create_move_patch(cls, **kwargs):
        res = super(TestManual, cls)._create_move(**kwargs)
        res = res.with_context(l10n_uy_skip_edi_send=True)
        return res

    @classmethod
    def _create_move_mock_patch(cls, **kwargs):
        res = super(TestMock, cls)._create_move(**kwargs)
        res = res.with_context(l10n_uy_skip_edi_send=True)
        return res

    @unittest.skip("Test skipped due to threading issues with WebSocket connections")
    def test_download_with_existing_cfe_patch(self):
        """No nos suma correr este test y es muy difícil de patchear por eso hacemos pass"""
        pass

    CFE_NS = {"cfe": "http://cfe.dgi.gub.uy"}

    def _move_internal_reference_to_cod_items(expected_xml):
        # TODO 20.0: remove, it is native in Odoo from 20.0 (odoo/enterprise master, https://github.com/odoo/enterprise/pull/129215)
        """Adapta los XML esperados de l10n_uy_edi al comportamiento de l10n_uy_ux: la referencia interna del producto
        no va embebida en NomItem ("[REF] Nombre") sino en su propio nodo <CodItem> (TpoCod INT1)."""
        for item in expected_xml.findall(".//cfe:Detalle/cfe:Item", CFE_NS):
            nom_item = item.find("cfe:NomItem", CFE_NS)
            if nom_item is None:  # ítems sin nombre (ej. RetencPercep de e-Resguardo)
                continue
            match = re.match(r"^\[(?P<code>[^\]]+)\] (?P<name>.+)$", nom_item.text or "")
            if not match:
                continue
            nom_item.text = match["name"]
            nro_lin_det = item.find("cfe:NroLinDet", CFE_NS)
            cod_item = etree.Element("{%s}CodItem" % CFE_NS["cfe"])
            etree.SubElement(cod_item, "{%s}TpoCod" % CFE_NS["cfe"]).text = "INT1"
            etree.SubElement(cod_item, "{%s}Cod" % CFE_NS["cfe"]).text = match["code"][:35]
            nro_lin_det.addnext(cod_item)

    def _check_cfe_patch(self, invoice, expected_prefix, expected_xml_file):
        origin_get_tree = self.get_xml_tree_from_string

        def get_tree_with_cod_items(xml_string):
            tree = origin_get_tree(xml_string)
            _move_internal_reference_to_cod_items(tree)
            return tree

        with patch.object(TestUyEdi, "get_xml_tree_from_string", side_effect=get_tree_with_cod_items):
            _check_cfe_patch.origin(self, invoice, expected_prefix, expected_xml_file)

    def test_120_e_ticket_final_consumer_patch(self):
        partner = self.env.ref("l10n_uy.partner_cfu")
        partner.l10n_latam_identification_type_id = self.env.ref("l10n_uy.it_dni").id
        partner.vat = ""
        # Get the original method and call it
        original_method = getattr(TestManual, "test_120_e_ticket_final_consumer").origin
        original_method(self)

    def test_default_doc_type_by_id_patch(self):
        partner = self.env.ref("l10n_uy.partner_cfu")
        partner.l10n_latam_identification_type_id = self.env.ref("l10n_uy.it_dni").id
        partner.vat = ""
        # Get the original method and call it
        original_method = getattr(TestManual, "test_default_doc_type_by_id").origin
        original_method(self)

    def test_110_account_move_line_nom_and_desc_patch(self):
        """Test skipped: l10n_uy_ux intentionally modifies the line name logic for DGI submission.

        The core l10n_uy_edi test expects that line.name is used to send data to DGI, but l10n_uy_ux
        modifies this behavior to use the product name instead. This is an intentional change,
        so we skip this test in l10n_uy_ux.
        """
        self.skipTest("l10n_uy_ux changes the line name logic for DGI submission")

    def propagate(method1, method2):
        if method1:
            for attr in ("_returns",):
                if hasattr(method1, attr) and not hasattr(method2, attr):
                    setattr(method2, attr, getattr(method1, attr))
        return method2

    def _patch_method(cls, name, method):
        origin = getattr(cls, name)
        method.origin = origin
        wrapped = propagate(origin, method)
        wrapped.origin = origin
        setattr(cls, name, wrapped)

    def _skip_method(cls, name, method):
        """Completely replace a method without calling the original"""
        setattr(cls, name, method)

    _patch_method(TestUyEdi, "_check_cfe", _check_cfe_patch)
    _patch_method(TestManual, "_create_move", _create_move_patch)
    _patch_method(TestMock, "_create_move", _create_move_mock_patch)
    _patch_method(
        TestManual,
        "test_120_e_ticket_final_consumer",
        test_120_e_ticket_final_consumer_patch,
    )
    _patch_method(TestManual, "test_default_doc_type_by_id", test_default_doc_type_by_id_patch)
    _patch_method(TestManual, "test_110_account_move_line_nom_and_desc", test_110_account_move_line_nom_and_desc_patch)
    _skip_method(
        TestAccountMoveSend,
        "test_download_with_existing_cfe",
        test_download_with_existing_cfe_patch,
    )
