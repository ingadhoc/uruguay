from odoo import Command
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("-at_install", "post_install", "post_install_l10n", "ux")
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
