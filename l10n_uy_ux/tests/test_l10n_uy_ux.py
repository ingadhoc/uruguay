from odoo import Command
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.exceptions import UserError
from odoo.tests import Form
from odoo.tests.common import tagged


@tagged("-at_install", "post_install", "post_install_l10n", "l10n_uy_ux")
class TestUx(TestUyEdi):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        self.company_uy.l10n_uy_edi_ucfe_env = "demo"

    def test_invalid_report_params(self):
        with self.assertRaisesRegex(UserError, "El parámetro 'reporte' contiene dos valores diferentes."):
            record = self.env["res.config.settings"].create(
                {"l10n_uy_report_params": "[['reporte', 'reporte'], ['secundario', 'ingles']]"}
            )
            record.uy_ux_onchange_l10n_uy_report_params()

    def _check_computed_params(self, value, expected_result):
        self.company_uy.l10n_uy_report_params = value
        invoice = self._create_move(
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.service_vat_22.id,
                        "price_unit": 100.0,
                    }
                ),
            ],
        )

        invoice.action_post()
        self._send_and_print(invoice)  # to generate the l10n_uy_edi.document
        result = invoice.l10n_uy_edi_document_id._get_report_params()
        self.assertEqual(result, expected_result, "Error in computed report parameters")

    def _check_automatic_params(self, expected_result):
        """Check if the automatic params are correctly set"""
        self.company_uy.l10n_uy_report_params = False
        invoice = self._create_move(
            invoice_line_ids=[
                Command.create(
                    {
                        "product_id": self.service_vat_22.id,
                        "price_unit": 100.0,
                    }
                ),
            ],
        )
        line_length = 140
        max_lines = 6
        invoice.narration = "A" * (line_length * max_lines + 10)
        invoice.action_post()
        self._send_and_print(invoice)
        result = invoice.l10n_uy_edi_document_id._get_report_params()
        self.assertEqual(result, expected_result, "Error in automatic report parameters")

    def test_without_report_params(self):
        """If not set any param should use standar PDF"""
        self._check_computed_params(False, ("ObtenerPdf", {}))
        self._check_computed_params("", ("ObtenerPdf", {}))
        self._check_computed_params("[]", ("ObtenerPdf", {}))

    def test_with_report_params(self):
        """If param set then should prepare correctly the report params to send"""
        self._check_computed_params(
            "[['adenda'], ['true']]",
            (
                "ObtenerPdfConParametros",
                {
                    "nombreParametros": {"string": ["adenda"]},
                    "valoresParametros": {"string": ["true"]},
                },
            ),
        )

        self._check_computed_params(
            "[['reporte'], ['ingles']]",
            (
                "ObtenerPdfConParametros",
                {
                    "nombreParametros": {"string": ["reporte"]},
                    "valoresParametros": {"string": ["ingles"]},
                },
            ),
        )

        self._check_computed_params(
            "[['reporte'], ['secundario']]",
            (
                "ObtenerPdfConParametros",
                {
                    "nombreParametros": {"string": ["reporte"]},
                    "valoresParametros": {"string": ["secundario"]},
                },
            ),
        )

        self._check_computed_params(
            "[['adenda', 'reporte'], ['true', 'ingles']]",
            (
                "ObtenerPdfConParametros",
                {
                    "nombreParametros": {"string": ["adenda", "reporte"]},
                    "valoresParametros": {"string": ["true", "ingles"]},
                },
            ),
        )

    def test_with_automatic_report_params(self):
        """If user does not set any param, it should take the automatic params from Odoo method"""
        self._check_automatic_params(
            (
                "ObtenerPdfConParametros",
                {
                    "nombreParametros": {"string": ["adenda"]},
                    "valoresParametros": {"string": ["true"]},
                },
            ),
        )

    def test_110_account_move_line_nom_and_desc(self):
        """Test account move with varied products and descriptions"""
        long_name = "Product name for testing purposes that intentionally contains more than eighty chars"

        products = [
            self.env["product.product"].create({"name": "Product Without Description"}),
            self.env["product.product"].create({"name": "Product With Description"}),
            self.env["product.product"].create({"name": long_name}),
        ]

        addenda = self.env["l10n_uy_edi.addenda"].create(
            {
                "content": "Addenda Content",
                "is_legend": False,
            }
        )

        # Define invoice lines data to create
        invoice_line_data = [
            {"product_id": products[0], "name": None, "addenda_ids": []},  # Without description
            {"product_id": products[1], "name": "Custom Description", "addenda_ids": []},  # With description
            {"product_id": products[2], "name": None, "addenda_ids": []},  # +80 chars without description
            {"product_id": products[2], "name": "Custom Description", "addenda_ids": []},  # +80 chars with description
            {"product_id": products[2], "name": None, "addenda_ids": [addenda]},  # +80 chars with addenda
            {
                "product_id": products[2],
                "name": "Custom Description",
                "addenda_ids": [addenda],
            },  # +80 chars with desc and addenda
            {"product_id": products[0], "name": False, "addenda_ids": []},  # With description deleted by user
            {"product_id": products[0], "name": "", "addenda_ids": []},  # With a empty string as description
        ]

        # Create invoice using Form to simulate UI interaction
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as invoice_form:
            invoice_form.partner_id = self.partner_local
            for line_data in invoice_line_data:
                with invoice_form.invoice_line_ids.new() as line_form:
                    line_form.product_id = line_data["product_id"]
                    # Only override name if explicitly provided (not None)
                    if line_data["name"] is not None:
                        line_form.name = line_data["name"]
                    # Add addenda if provided
                    if line_data["addenda_ids"]:
                        line_form.l10n_uy_edi_addenda_ids.clear()
                        for addenda_rec in line_data["addenda_ids"]:
                            line_form.l10n_uy_edi_addenda_ids.add(addenda_rec)

        invoice = invoice_form.save()

        for idx, line in enumerate(invoice.invoice_line_ids):
            nom_item, description = invoice._l10n_uy_edi_get_line_nom_and_desc(line)
            if idx == 0:  # Without description
                self.assertEqual(
                    nom_item, "Product Without Description"[:80], "NomItem mismatch for line without description"
                )
                self.assertEqual(description, "", "Description mismatch for line without description")
            elif idx == 1:  # With custom description (aml.name is the custom description)
                self.assertEqual(nom_item, "Custom Description"[:80], "NomItem mismatch for line with description")
                self.assertEqual(description, "", "Description mismatch for line with description")
            elif idx == 2:  # +80 chars without description
                self.assertEqual(
                    nom_item, long_name[:80], "NomItem mismatch for line with long name without description"
                )
                self.assertEqual(
                    description, long_name[80:], "Description mismatch for line with long name without description"
                )
            elif idx == 3:  # +80 chars with custom description (aml.name is the custom description)
                self.assertEqual(
                    nom_item, "Custom Description"[:80], "NomItem mismatch for line with long name and description"
                )
                self.assertEqual(
                    description,
                    "",
                    "Description mismatch for line with long name and description",
                )
            elif idx == 4:  # +80 chars with addenda
                self.assertEqual(nom_item, long_name[:80], "NomItem mismatch for line with long name and addenda")
                self.assertIn(
                    "Addenda Content", description, "Addenda content missing in description for line with addenda"
                )
            elif idx == 5:  # +80 chars with custom description and addenda (aml.name is the custom description)
                self.assertEqual(
                    nom_item,
                    "Custom Description"[:80],
                    "NomItem mismatch for line with long name, description, and addenda",
                )
                # When custom description is set, description should contain the addenda
                self.assertIn(
                    "Addenda Content",
                    description,
                    "Addenda content missing in description for line with desc and addenda",
                )
            elif idx == 6 or idx == 7:  # With description deleted by user or "" (aml.name is False or empty)
                self.assertEqual(nom_item, "-", "NomItem mismatch for line with deleted description")
                self.assertEqual(description, "", "Description mismatch for line with deleted description")
