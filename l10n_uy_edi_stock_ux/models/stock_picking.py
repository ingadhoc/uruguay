from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = "stock.picking"

    # Fields

    l10n_uy_cfe_xml = fields.Text("Technical field to preview the xml")

    def _l10n_uy_stock_cfe_B_details(self):
        """Agregamos a cada línea del detalle del e-Remito los códigos del ítem (B2 TpoCod, B3 Cod: nodo <CodItem>),
        que Odoo no informa, y dejamos NomItem sin el prefijo de la referencia interna (el código viaja en CodItem).
        Ver product.product._l10n_uy_edi_get_cod_items (l10n_uy_ux)."""
        # TODO 20.0: remove, it is native in Odoo from 20.0 (odoo/enterprise master, https://github.com/odoo/enterprise/pull/129215)
        res = super()._l10n_uy_stock_cfe_B_details()
        # l10n_uy_edi_stock arma un ítem por cada move_line_ids, en el mismo orden
        for line, item in zip(self.move_line_ids, res):
            product = line.product_id
            item["CodItem"] = product._l10n_uy_edi_get_cod_items()
            nom_item = product.with_context(display_default_code=False).display_name or line.display_name
            item["NomItem"] = nom_item[:80]
        return res

    # Buttons

    def uy_stock_action_get_pdf(self):
        """Permite volver a generar el PDF cuando no existe, sea que hubo error
        porque no se creo o alguien lo borro sin querer"""
        self.ensure_one()
        self.l10n_uy_edi_pdf_report_id.res_field = False
        result = self._l10n_uy_edi_get_pdf()
        if pdf_file := result.get("pdf_file"):
            pdf_file.register_as_main_attachment()
            self.invalidate_recordset(fnames=["l10n_uy_edi_pdf_report_id", "l10n_uy_edi_pdf_report_file"])
        else:
            raise UserError(_("Could not generate the PDF"))

    def uy_stock_action_preview_xml(self):
        """En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.

        Este es un nuevo boton preview que permite pre visualizar el contenido del xml en cualquier momento, incluso
        cuando la factura aun esta en estado borrador."""
        self.l10n_uy_cfe_xml = self._l10n_uy_edi_get_xml_content().encode()

    def uy_stock_action_validate_cfe(self):
        """Check CFE XML valid files: 350: Validación de estructura de CFE

        To make the validation of the CFE and connect to uwaure we need to have a EDI document
        For that reason if we have one we delete it and create a new one with the result of
        the validation, since we are raising and the end of the method then the edi document
        is rolled back"""
        self.ensure_one()

        self.l10n_uy_edi_document_id.unlink()
        edi_doc = self.env["l10n_uy_edi.document"].create(
            {
                "picking_id": self.id,
                "uuid": self.env["l10n_uy_edi.document"]._get_uuid(self),
            }
        )
        self.l10n_uy_edi_document_id = edi_doc

        result = edi_doc._ucfe_inbox("350", {"CfeXmlOTexto": self.l10n_uy_cfe_xml})
        response = result.get("response")
        if response is not None:
            cod_rta = response.findtext(".//{*}CodRta")
            if cod_rta != "00":
                edi_doc._update_cfe_state(result)
                edi_doc.message = _("Error creating CFẸ XML") + "\n\n" + edi_doc.message
                raise UserError(
                    _("Error creating CFẸ XML\n\n %(errors)s", errors=response.findtext(".//{*}MensajeRta"))
                )

        raise UserError(_("Valid XML"))
