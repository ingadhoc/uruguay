from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = "stock.picking"

    # Fields

    l10n_uy_cfe_xml = fields.Text("Technical field to preview the xml")
    manual_uruware_invoice = fields.Char()

    # Buttons

    def l10n_uy_edi_create_delivery_guide(self):
        """Extends l10n_uy_edi_create_invoice to create the edi document for the delivery guide
        that has been previously validated in Uruware"""
        # TODO: validar
        # We check that the l10n_uy_edi_cfe_uuid has been manually set and we consult Uruware to get the invoice information
        pickings = self.env["stock.picking"]
        validated_pickings = pickings.filtered(
            lambda x: x.l10n_uy_edi_cfe_uuid
            and not x.l10n_uy_edi_document_id.attachment_id
            and not x.l10n_uy_edi_cfe_state
        )
        if validated_pickings:
            validated_pickings.uy_stock_action_get_uruware_cfe()
        return super(StockPicking, validated_pickings).l10n_uy_edi_create_delivery_guide()

    def uy_stock_action_get_pdf(self):
        """Permite volver a generar el PDF cuando no existe, sea que hubo error
        porque no se creo o alguien lo borro sin querer"""
        self.ensure_one()
        self.edi_pdf_report_id.res_field = False
        result = self._l10n_uy_edi_get_pdf()
        if pdf_file := result.get("pdf_file"):
            pdf_file.register_as_main_attachment()
            self.invalidate_recordset(fnames=["edi_pdf_report_id", "edi_pdf_report_file"])

    def uy_stock_action_preview_xml(self):
        """En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.

        Este es un nuevo boton preview que permite pre visualizar el contenido del xml en cualquier momento, incluso
        cuando la factura aun esta en estado borrador."""
        self.l10n_uy_cfe_xml = self._l10n_uy_stock_get_xml_content().encode()

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

        raise UserError(_("XML Valido"))

    def uy_stock_action_get_uruware_cfe(self):
        """Boton visible en la solapa DGI que permite con el dato del UUID cargar el remito creado en
        Uruware postmorten en el Odoo

        (INBOX 360 - Consulta de estado de CFE).

        Los datos que sincroniza son

            * numero de documento
            * tipo de documento
            * estado del comprobante
            - crea el EDI document
            - agregar el pdf de la factura
        """

        # Filtrar solo los e-remitos
        uy_pickings = self.filtered(
            lambda x: x.country_code == "UY"
            and x.picking_type_code == "outgoing"
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_edi_cfe_state not in ["accepted", "rejected", "received"]
        )

        for picking in uy_pickings:
            if not picking.manual_uruware_invoice:
                raise UserError(_("You need to define 'CFE Key or UUID' in order to continue"))
            edi_doc = self.env["l10n_uy_edi.document"].create(
                {
                    "picking_id": picking.id,
                    "uuid": self.manual_uruware_invoice,
                }
            )
            picking.l10n_uy_edi_document_id = edi_doc
            result = edi_doc._ucfe_inbox("360", {"Uuid": edi_doc.uuid})
            edi_doc._update_cfe_state(result)
            response = result.get("response")
            if response is not None:
                uy_doc_code = response.findtext(".//{*}TipoCfe")
                serie = response.findtext(".//{*}Serie")
                doc_number = response.findtext(".//{*}NumeroCfe")
                picking.write(
                    {
                        "l10n_latam_document_number": serie + "%07d" % int(doc_number),
                        "l10n_latam_document_type_id": picking.filtered(lambda x: x.code == uy_doc_code).id,
                    }
                )
                picking.uy_stock_action_get_pdf()
