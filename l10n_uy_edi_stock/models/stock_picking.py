<<<<<<< HEAD
||||||| MERGE BASE
=======
import base64
import logging

from lxml import etree
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.addons.l10n_uy_edi.models.account_move import format_float
from odoo.exceptions import UserError
from odoo.tools import html2plaintext
from odoo.tools.xml_utils import cleanup_xml_node

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["l10n.uy.cfe", "stock.picking"]

    _inherit = "stock.picking"

    # Need to make it work with document types
    l10n_latam_document_type_id = fields.Many2one("l10n_latam.document.type", string="Document Type (UY)", copy=False)
    l10n_latam_document_number = fields.Char(string="Document Number (UY)", readonly=True, copy=False)
    l10n_latam_available_document_type_ids = fields.Many2many(
        "l10n_latam.document.type",
        compute="_compute_l10n_latam_available_document_types",
    )

    # Need to make it work with EDI (simil to what we have in invoices)
    l10n_uy_edi_document_id = fields.Many2one("l10n_uy_edi.document", string="Uruguay E-Invoice CFE", copy=False)
    l10n_uy_edi_cfe_uuid = fields.Char(related="l10n_uy_edi_document_id.uuid")
    l10n_uy_edi_cfe_state = fields.Selection(related="l10n_uy_edi_document_id.state", store=True)
    l10n_uy_edi_error = fields.Text(related="l10n_uy_edi_document_id.message")
    l10n_uy_is_cfe = fields.Boolean(
        compute="_compute_l10n_uy_is_cfe",
        help="Campo tecnico para saber si es un comprobante electronico o no y usarlo en la vista para mostrar o requerir ciertos campos."
        " por los momentos lo estamos usando solo para remitos pero podemos extenderlo para otros modelos",
    )
    l10n_uy_edi_addenda_ids = fields.Many2many(
        "l10n_uy_edi.addenda",
        string="Addenda & Disclosure",
        domain="[('type', 'in', ['issuer', 'receiver', 'cfe_doc', 'addenda'])]",
        help="Addendas and Mandatory Disclosure to add on the CFE. They can be added either to the issuer, receiver,"
        " cfe doc additional info section or to the addenda section. However, the item type should not be set in"
        " this field; instead, it should be specified in the invoice lines.",
        ondelete="restrict",
    )

    # Solo Remito Exportacion
    # l10n_uy_edi_cfe_sale_mode = fields.Selection([
    #     ("1", "General Regime"),
    #     ("2", "Consignment"),
    #     ("3", "Reviewable Price"),
    #     ("4", "Own goods to customs exclaves"),
    #     ("90", "General Regime - exportation of services"),
    #     ("99", "Other transactions"),
    #     ], "Sales Modality (EDI)",
    # )
    # l10n_uy_edi_cfe_transport_route = fields.Selection([
    #     ("1", "Maritime"),
    #     ("2", "Air"),
    #     ("3", "Ground"),
    #     ("8", "N/A"),
    #     ("9", "Other"),
    #     ], "Transportation Route",
    # )

    l10n_uy_edi_related_docs_ids = fields.Many2many(
        "l10n_uy_edi.document",
        string="Related Documents",
        domain="[('picking_id', '!=', False), ('picking_id.partner_id', '=', partner_id), ('state', 'in', ['accepted', 'received', 'rejected'])]",
        help="Related electronic documents",
    )

    l10n_uy_transfer_of_goods = fields.Selection(
        [("1", "Venta"), ("2", "Traslados internos")],
        string="Traslados de Bienes",
        default=False,
        copy=False,
    )
    l10n_uy_edi_place_of_delivery = fields.Char(
        "Place of Delivery",
        size=100,
        help="CFE: Indication of where the merchandise is delivered or the service is provided"
        " (Address, Branch, Port, etc.) if True then we will inform the shipping address's name and street",
    )
    edi_pdf_report_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="PDF Attachment",
        compute=lambda self: self._compute_linked_attachment_id("edi_pdf_report_id", "edi_pdf_report_file"),
        depends=["edi_pdf_report_file"],
    )
    edi_pdf_report_file = fields.Binary(
        attachment=True,
        string="PDF File",
        copy=False,
    )
    l10n_uy_edi_xml_attachment_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Uruguay E-Invoice XML",
        compute="_compute_l10n_uy_edi_xml_attachment_id",
        help="Uruguay: the most recent e-invoice XML returned by Uruware.",
    )

    l10n_uy_cfe_xml = fields.Text("Technical field to preview the xml")
    manual_uruware_invoice = fields.Char()

    # Onchange methods

    @api.onchange("l10n_uy_transfer_of_goods")
    def onchange_transfer_of_goods(self):
        if self.l10n_uy_transfer_of_goods:
            self.l10n_latam_document_type_id = self.l10n_latam_available_document_type_ids.filtered(
                lambda x: x.code == "181"
            )  # e-Delivery Guide Document
        else:
            self.l10n_latam_document_type_id = False

    # Compute methods

    @api.depends("l10n_uy_edi_document_id.state")
    def _compute_l10n_uy_edi_xml_attachment_id(self):
        for move in self:
            doc = move.l10n_uy_edi_document_id
            move.l10n_uy_edi_xml_attachment_id = doc.state in ["accepted", "received", "rejected"] and doc.attachment_id

    @api.depends("l10n_latam_document_number")
    def _compute_display_name(self):
        """Display: 'Stock Picking Internal Sequence : Delivery Guide Number (if defined)'"""
        super()._compute_display_name()
        for picking in self.filtered(lambda x: x.l10n_latam_document_number):
            picking.display_name = picking.name + ": (%s %s)" % (
                picking.l10n_latam_document_type_id.doc_code_prefix,
                picking.l10n_latam_document_number,
            )

    def _compute_l10n_uy_is_cfe(self):
        for rec in self:
            rec.l10n_uy_is_cfe = False
            if (
                rec.country_code == "UY"
                and rec.picking_type_code == "outgoing"
                and rec.l10n_latam_document_type_id.code in ["124", "181", "224", "281"]
            ):
                rec.l10n_uy_is_cfe = True

    @api.depends("partner_id", "company_id", "picking_type_code")
    def _compute_l10n_latam_available_document_types(self):
        uy_pickings = self.filtered(lambda x: x.country_code == "UY" and x.picking_type_code == "outgoing")
        uy_pickings.l10n_latam_available_document_type_ids = self.env["l10n_latam.document.type"].search(
            self._get_l10n_latam_documents_domain()
        )
        (self - uy_pickings).l10n_latam_available_document_type_ids = False

    def _compute_linked_attachment_id(self, attachment_field, binary_field):
        """Helper to retreive Attachment from Binary fields
        This is needed because fields.Many2one('ir.attachment') makes all
        attachments available to the user.
        """
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "in", self.ids),
                ("res_field", "=", binary_field),
            ]
        )
        move_vals = {att.res_id: att for att in attachments}
        for move in self:
            move[attachment_field] = move_vals.get(move._origin.id, False)

    # Buttons

    def action_cancel(self):
        """El remito no puede ser modificado una vez que ya fue aceptado por DGI"""
        if self.filtered(
            lambda x: x.l10n_uy_is_cfe and x.l10n_uy_edi_cfe_state in ["accepted", "rejected", "received"]
        ):
            raise UserError(_("Can not cancel a Delivery Guide already process by DGI"))
        return super().action_cancel()

    def l10n_uy_edi_action_get_dgi_state(self):
        self.l10n_uy_edi_document_id.action_update_dgi_state()
        rejected_pickings = self.filtered(lambda x: x.l10n_uy_edi_cfe_state == "rejected")
        if rejected_pickings:
            _logger.info(
                "Rejected picking(s): %s",
                [(rec.id, rec.name) for rec in rejected_pickings],
            )
            for picking in rejected_pickings:
                picking.message_post(
                    body=self.env._(
                        "The CFE has been rejected by DGI. Please, manually check the reject reason "
                        "and generate/send a new CFE with the fixes"
                    ),
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )

    def l10n_uy_edi_send_dgi(self):
        """El E-remito tiene las siguientes partes en el xml
        A. Encabezado
        B. Detalle de los productos
        C. Subtotales Informativos (opcional)
        F. Informacion de Referencia (condicional)
        """
        # Filtrar solo los e-remitos
        uy_delivery_guides = self.filtered(
            lambda x: (
                x.country_code == "UY"
                and x.picking_type_code == "outgoing"
                and x.l10n_latam_document_type_id
                and int(x.l10n_latam_document_type_id.code) > 0
                and x.l10n_uy_edi_cfe_state not in ["accepted", "rejected", "received"]
            )
        )

        # If the invoice was previously validated in Uruware and need to be link to Odoo
        # we check that the l10n_uy_edi_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_delivery_guides.filtered(
            lambda x: (
                x.l10n_uy_edi_cfe_uuid and not x.l10n_uy_edi_document_id.attachment_id and not x.l10n_uy_edi_cfe_state
            )
        )
        if pre_validated_in_uruware:
            pre_validated_in_uruware.uy_stock_action_get_uruware_cfe()
            uy_delivery_guides = uy_delivery_guides - pre_validated_in_uruware

        if not uy_delivery_guides:
            return

        uy_delivery_guides.mapped("company_id")._check_env()

        # Send invoices to DGI and get the return info
        msg = ""
        for picking in uy_delivery_guides:
            edi_doc = self.env["l10n_uy_edi.document"].create(
                {
                    "picking_id": picking.id,
                    "uuid": self.env["l10n_uy_edi.document"]._get_uuid(picking),
                }
            )
            picking.l10n_uy_edi_document_id = edi_doc

            if picking.company_id.l10n_uy_edi_ucfe_env == "demo":
                attachments = picking._l10n_uy_edi_dummy_validation()
                msg = _(
                    "This CFE has been generated in DEMO Mode. It is considered"
                    ' as accepted and it won"t be sent to DGI.'
                )
            else:
                request_data = picking._l10n_uy_stock_prepare_req_data()
                result = edi_doc._send_dgi(request_data)
                edi_doc._update_cfe_state(result)

                response = result.get("response")

                if edi_doc.message:
                    picking.message_post(
                        body=Markup("<font style='color:Tomato;'><strong>{}:</strong></font> <i>{}</<i>").format(
                            ("ERROR"), edi_doc.message
                        )
                    )
                elif edi_doc.state in ["received", "accepted"]:
                    # If everything is ok we save the return information
                    picking.l10n_latam_document_number = response.findtext(".//{*}Serie") + "%07d" % int(
                        response.findtext(".//{*}NumeroCfe")
                    )

                    msg = response.findtext(".//{*}MensajeRta", "")
                    msg += _("The electronic invoice was created successfully")

                if response is not None:
                    attachments = picking._l10n_uy_stock_update_xml_and_pdf_file(response)

            picking.with_context(no_new_invoice=True).message_post(
                body=msg, attachment_ids=attachments.ids if attachments else False
            )

    def uy_stock_action_get_pdf(self):
        """Permite volver a generar el PDF cuando no existe, sea que hubo error
        porque no se creo o alguien lo borro sin querer"""
        self.ensure_one()
        self.edi_pdf_report_id.res_field = False
        result = self._l10n_uy_edi_get_pdf()
        if pdf_file := result.get("pdf_file"):
            pdf_file.register_as_main_attachment()
            self.invalidate_recordset(fnames=["edi_pdf_report_id", "edi_pdf_report_file"])

    def l10n_uy_edi_action_download_preview_xml(self):
        if self.l10n_uy_edi_document_id.attachment_id:
            return self.l10n_uy_edi_document_id.action_download_file()

    # Helpers

    def _get_l10n_latam_documents_domain(self):
        """return domain"""
        codes = self._l10n_uy_get_delivery_guide_codes()
        return [
            ("code", "in", codes),
            ("code", "!=", "0"),
            ("active", "=", True),
            ("internal_type", "=", "stock_picking"),
        ]

    def _l10n_uy_stock_update_xml_and_pdf_file(self, response):
        """Clean up the pdf and xml fields. Create new ones with the response"""
        self.ensure_one()
        res_files = self.env["ir.attachment"]
        edi_doc = self.l10n_uy_edi_document_id

        # TODO KZ this should not necessary :(
        edi_doc._compute_from_origin()

        self.edi_pdf_report_id.res_field = False
        edi_doc.attachment_id.res_field = False

        xml_content = response.findtext(".//{*}XmlCfeFirmado")
        if xml_content:
            res_files = self.env["ir.attachment"].create(
                {
                    "res_model": "l10n_uy_edi.document",
                    "res_field": "attachment_file",
                    "res_id": edi_doc.id,
                    "name": edi_doc._get_xml_attachment_name(),
                    "type": "binary",
                    "datas": base64.b64encode(
                        xml_content.encode()
                        if self.l10n_uy_edi_cfe_state in ["received", "accepted"]
                        else self._l10n_uy_stock_get_xml_content().encode()
                    ),
                }
            )

            edi_doc.invalidate_recordset(["attachment_id", "attachment_file"])

            # If the record has been posted automatically print and attach the legal report to the record.
            if self.l10n_uy_edi_cfe_state and self.l10n_uy_edi_cfe_state != "error":
                pdf_result = self._l10n_uy_edi_get_pdf()
                if pdf_file := pdf_result.get("pdf_file"):
                    # make sure latest PDF shows to the right of the chatter
                    pdf_file.register_as_main_attachment(force=True)
                    self.invalidate_recordset(fnames=["edi_pdf_report_id", "edi_pdf_report_file"])
                    res_files |= pdf_file
        else:
            self._l10n_uy_edi_get_preview_xml()
        return res_files

    def _l10n_uy_edi_dummy_validation(self):
        # COPY l10n_uy_edi (only change move_id with picking_id)
        """When we want to skip DGI and validate only in Odoo"""
        edi_doc = self.l10n_uy_edi_document_id
        edi_doc.state = "accepted"
        self.write(
            {
                "l10n_latam_document_number": "DE%07d" % (edi_doc.picking_id.id),
                # "ref": "*DEMO",
            }
        )

        return self._l10n_uy_edi_get_preview_xml()

    def _l10n_uy_edi_get_preview_xml(self):
        # COPY l10n_uy_edi
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        edi_doc.attachment_id.res_field = False
        xml_file = self.env["ir.attachment"].create(
            {
                "res_model": "l10n_uy_edi.document",
                "res_field": "attachment_file",
                "res_id": edi_doc.id,
                "name": edi_doc._get_xml_attachment_name(),
                "type": "binary",
                "datas": base64.b64encode(self._l10n_uy_stock_get_xml_content().encode()),
            }
        )
        edi_doc.invalidate_recordset(["attachment_id", "attachment_file"])
        return xml_file

    def _l10n_uy_edi_get_pdf(self):
        """Call endpoint to get PDF file from Uruware (Standard Representation)
        return: dictionary with {"errors": str(): "pdf_file"attachment object }"""
        res = {}
        result = self.l10n_uy_edi_document_id._get_pdf()
        if file_content := result.get("file_content"):
            pdf_file = self.env["ir.attachment"].create(
                {
                    "res_model": "stock.picking",
                    "res_id": self.id,
                    "res_field": "edi_pdf_report_file",
                    "name": self.l10n_uy_edi_document_id._get_xml_attachment_name().replace(".xml", ".pdf"),
                    "type": "binary",
                    "datas": file_content,
                }
            )
            res["pdf_file"] = pdf_file

        if errors := result.get("errors"):
            msg = _("Error getting the PDF file: %s", errors)
            self.l10n_uy_edi_error = (self.l10n_uy_edi_error or "") + msg
            self.message_post(body=msg)

        return res

    def _l10n_uy_edi_get_addenda(self):
        """return string with the addenda of the remito"""
        addenda = self.l10n_uy_edi_document_id._get_legends("addenda", self)
        if self.origin:
            addenda += "\n\nOrigin: %s" % self.origin
        if self.note:
            addenda += "\n\n%s" % html2plaintext(self.note)
        return addenda.strip()

    def _l10n_uy_get_delivery_guide_codes(self):
        """return list of the available document type codes for uruguayan of stock picking"""
        # self.ensure_one()
        # if self.picking_type_code != 'outgoing':
        #     return []
        return ["0", "181"]

    # XML prepapre values

    def _l10n_uy_stock_prepare_req_data(self):
        """Creating dictionary with the request to generate a DGI EDI document"""
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        xml_content = self._l10n_uy_stock_get_xml_content()
        req_data = {
            "Uuid": edi_doc.uuid,
            "TipoCfe": int(self.l10n_latam_document_type_id.code),
            "HoraReq": edi_doc.request_datetime.strftime("%H%M%S"),
            "FechaReq": edi_doc.request_datetime.date().strftime("%Y%m%d"),
            "CfeXmlOTexto": xml_content,
        }

        if addenda := self._l10n_uy_edi_get_addenda():
            req_data["Adenda"] = addenda
        return req_data

    def _uy_get_cfe_lines(self):
        self.ensure_one()
        # Cuando está validado el remito siempre usa move_line_ids
        # Usamos move_ids_without_package para Stock moves "not in package" (stock.move)
        # move_line_ids	para Operations (stock.move.line)
        # move_line_ids_without_package	para Operations "without package" (stock.move.line)
        return self.move_line_ids

    def _l10n_uy_stock_get_xml_content(self):
        """Create the CFE xml structure and validate it
        :return: string the xml content to send to DGI"""
        self.ensure_one()
        template_name = "l10n_uy_edi_stock." + self.l10n_uy_edi_document_id._get_cfe_tag(self) + "_template"
        values = {
            "cfe": self,
            "res_model": self._name,
            "IdDoc": self._l10n_uy_stock_cfe_A_iddoc(),
            "emisor": self._l10n_uy_stock_cfe_A_issuer(),
            "receptor": self._l10n_uy_stock_cfe_A_receptor(),
            "totals_detail": self._l10n_uy_stock_cfe_A_totals(),
            "item_detail": self._l10n_uy_stock_cfe_B_details(),
            "referencia_lines": self._l10n_uy_edi_cfe_F_reference(),
            "format_float": format_float,
        }
        cfe = self.env["ir.qweb"]._render(template_name, values=values)
        return etree.tostring(cleanup_xml_node(cfe)).decode()

    def _l10n_uy_stock_cfe_A_iddoc(self):
        """XML Section A (Encabezado)"""
        values = {
            "TipoCFE": self.l10n_latam_document_type_id.code,
            "FchEmis": self.scheduled_date.date(),
            "TipoTraslado": self.l10n_uy_transfer_of_goods,  # A5
        }

        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "ModVenta": self.l10n_uy_edi_cfe_sale_mode or None,  # A14
        #         "ViaTransp": self.l10n_uy_edi_cfe_transport_route or None,  # A15
        #     })

        empty_values = {}.fromkeys(
            [
                "MntBruto",
                "FmaPago",
                "FchVenc",
                "ClauVenta",
                "InfoAdicionalDoc",
                "ModVenta",
                "ViaTransp",
            ],
            None,
        )
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_issuer(self):
        return {
            "RUCEmisor": self.company_id.vat,
            "RznSoc": self.company_id.name[:150],
            "CdgDGISucur": self.company_id.l10n_uy_edi_branch_code,
            "DomFiscal": self.company_id.partner_id._l10n_uy_edi_get_fiscal_address(),
            "Ciudad": (self.company_id.city or "")[:30] or None,
            "Departamento": (self.company_id.state_id.name or "")[:30] or None,
            "InfoAdicionalEmisor": self.l10n_uy_edi_document_id._get_legends("issuer", self) or None,
        }

    def _l10n_uy_stock_cfe_A_receptor(self):
        """XML Section A (Encabezado / Receptor)"""
        self.ensure_one()
        doc_type = self.partner_id._l10n_uy_edi_get_doc_type()
        values = {
            "TipoDocRecep": doc_type or None,  # A60
            "CodPaisRecep": self.partner_id.country_id.code or ("UY" if doc_type in [2, 3] else "99"),  # A61
            "DocRecep": self.partner_id.vat if doc_type in [1, 2, 3] else None,  # A62
            "DocRecepExt": self.partner_id.vat if doc_type not in [1, 2, 3] else None,  # A62.1
            "RznSocRecep": self.partner_id.name[:150] or None,  # A63
            "DirRecep": self.partner_id._l10n_uy_edi_get_fiscal_address() or None,  # A64
            "CiudadRecep": self.partner_id.city and self.partner_id.city[:30] or None,  # A65
            "DeptoRecep": self.partner_id.state_id and self.partner_id.state_id.name[:30] or None,  # A66
            "PaisRecep": self.partner_id.country_id and self.partner_id.country_id.name or None,  # A66.1
            "InfoAdicional": self.l10n_uy_edi_document_id._get_legends("receiver", self) or None,  # A68
            "LugarDestEnt": self.l10n_uy_edi_place_of_delivery or None,  # A69
        }
        empty_values = {}.fromkeys(["CompraID"], None)
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_totals(self):
        """XML Section C (SUBTOTALES INFORMATIVOS)"""
        self.ensure_one()
        lines = self._uy_get_cfe_lines()
        res = {
            "CantLinDet": len(lines),  # A126
        }

        # currency_name = self.company_id.currency_id.name if self.company_id.currency_id else None
        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "MntExpoyAsim": sum(self.move_line_ids.mapped('quantity')) or None,
        #         "TpoMoneda": currency_name if not self.l10n_latam_document_type_id.code == '181' else None,  # A110
        #         'TpoCambio': None if currency_name == "UYU" else self._l10n_uy_edi_get_used_rate() or None,  # A111
        #     })

        empty_values = {}.fromkeys(
            [
                "MntNoGrv",
                "MntNetoIvaTasaMin",
                "MntNetoIVATasaBasica",
                "MntNetoIVAOtra",
                "IVATasaMin",
                "IVATasaBasica",
                "MntIVATasaMin",
                "MntIVATasaBasica",
                "MntIVAOtra",
                "MntTotal",
                "MontoNF",
                "MntPagar",
                "TpoMoneda",
                "TpoCambio",
                "MntExpoyAsim",
            ],
            None,
        )
        res.update(empty_values)
        return res

    def _l10n_uy_stock_cfe_B_details(self):
        self.ensure_one()
        res = []

        # Solo Remito de Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     invoice_ind = 10  # For B4

        for k, line in enumerate(self.move_line_ids, start=1):
            temp = {
                "NroLinDet": k,  # B1
                "IndFact": None,  # B4
                "NomItem": line.display_name,  # B7
                "DscItem": line.description_picking
                if line.description_picking and line.description_picking != line.display_name
                else None,  # B8
                "Cantidad": line.quantity,  # B9
                "UniMed": line.product_uom_id.name[:4] if line.product_uom_id else "N/A",  # B10
                # "PrecioUnitario": line.price_unit,  # B11 como encuentro el precio unitario para facturas de expo ?
                # "MontoItem": line.price_total if tax_included else line.price_subtotal,  # B24 como encuentro el precio unitario para facturas de expo ?
            }
            empty_values = {}.fromkeys(
                [
                    "PrecioUnitario",
                    "DescuentoPct",
                    "DescuentoMonto",
                    "MontoItem",
                ],
                None,
            )
            temp.update(empty_values)
            res.append(temp)

        return res

    def _l10n_uy_edi_cfe_F_reference(self):
        """XML Section F (REFERENCE INFORMATION)"""
        self.ensure_one()
        res = []
        related_docs = self.l10n_uy_edi_related_docs_ids
        for k, related_cfe in enumerate(related_docs, 1):
            cfe_serie, cfe_number = self.l10n_uy_edi_document_id._get_doc_parts(related_cfe)
            res.append(
                {
                    "NroLinRef": k,  # F1
                    "TpoDocRef": int(related_cfe.l10n_latam_document_type_id.code),  # F3
                    "Serie": cfe_serie,  # F4
                    "NroCFERef": cfe_number,  # F5
                }
            )
        return res

    # TODO need to re adapt

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
                    _(
                        "Error creating CFẸ XML\n\n %(errors)s",
                        errors=response.findtext(".//{*}MensajeRta"),
                    )
                )

        raise UserError(_("XML Valido"))

    # def _l10n_uy_edi_get_used_rate(self):
    #     # COPY l10n_uy_edi
    #     self.ensure_one()
    #     # We need to use abs to avoid error on Credit Notes (amount_total_signed is negative)
    #     return abs(self.amount_total_signed) / self.amount_total

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
            lambda x: (
                x.country_code == "UY"
                and x.picking_type_code == "outgoing"
                and x.l10n_latam_document_type_id
                and int(x.l10n_latam_document_type_id.code) > 0
                and x.l10n_uy_edi_cfe_state not in ["accepted", "rejected", "received"]
            )
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
            # EL response no me trae los datos que necesito, solamente me trajo
            # Created: 2024-11-28T01:08:09.899Z
            # Expires: 2024-11-28T01:13:09.899Z
            # ErrorCode: 0
            # CodComercio: Sumila-8485
            # CodRta: 11
            # CodTerminal: FC-8485
            # FechaFirma: 2024-11-27T22:03:30.0000000-03:00
            # TipoMensaje: 361
            # Uuid: C2753E92-A51C-404F-A91F-5C3875862402
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

    def _l10n_uy_edi_stock_cron_update_dgi_status(self, batch_size=10):
        """Cron to update the DGI status of the stock pickings"""
        domain = [
            ("l10n_uy_is_cfe", "=", True),
            ("l10n_uy_edi_cfe_state", "=", "received"),
        ]
        pickings = self.env["stock.picking"].search(domain, limit=batch_size, order="id")
        pickings.l10n_uy_edi_action_get_dgi_state()

        if self.env["stock.picking"].search_count(domain) > batch_size:
            self.env.ref("l10n_uy_edi_stock.ir_cron_update_dgi_state_pickings")._trigger()

>>>>>>> FORWARD PORTED
