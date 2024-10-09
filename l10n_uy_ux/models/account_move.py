import base64
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from odoo import api, models, fields, _

from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, safe_eval
from odoo.tools.misc import formatLang


_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = "account.move"

    l10n_uy_idreq = fields.Char(
        "idReq", copy=False, readonly=True, groups="base.group_system",
        help="Uruware Notification ID that lets us sync vendor bill data.")

    l10n_uy_cfe_xml = fields.Text(
        "XML CFE", copy=False, groups="base.group_system",
        help="Technical field used to preview the XML content for both customer invoices"
        " before sending and for vendor bills")

    l10n_latam_document_type_id = fields.Many2one(change_default=True)
    # This is needed to be able to save default values
    # TODO KZ hacer pr a 17 o master pidiendo que hagan este fix directamtne en el modulo de l10n_latam_base

    # EXTENDS

    def _l10n_uy_edi_get_addenda(self):
        # EXTEND l10n_uy_edi
        """ Agrega el campo referencia compo parte de la adenda """
        self.ensure_one()
        res = super()._l10n_uy_edi_get_addenda()
        if self.ref:
            res += "\n\n" + _("Reference") + ": %s" % self.ref
        return res

    def _l10n_uy_edi_check_move(self):
        # EXTEND l10n_uy_edi
        """ Validaciones previas a enviar a DGI que Odoo no nos acepto

            - Que el diario este bien configurado antes de emitir
            - Que las momendas esten bien configuradas
            - Que los impuestos IVA 0 10 y 22 existan en la companñia
        """
        self.ensure_one()
        errors = super()._l10n_uy_edi_check_move()

        currency_names = self.currency_id.mapped("name") + self.company_id.currency_id.mapped("name")
        if not currency_names:
            errors.append(_("You need to configure the company currency"))

        if self.journal_id.type == "sale" and self.journal_id.l10n_uy_edi_type not in ["electronic", "manual"]:
            errors.append(_("Missing uruguayan invoicing type on journal %s.", self.name))

        # VAT Configuration
        for company in self.company_id:
            taxes = self.env["account.tax"].search([("company_id", "=", company.id), ("l10n_uy_tax_category", "=", "vat")])
            tax_22 = taxes.filtered(lambda x: x.amount == 22)
            tax_10 = taxes.filtered(lambda x: x.amount == 10)
            tax_0 = taxes.filtered(lambda x: x.amount == 0)
            if not tax_22 or not tax_10 or not tax_0:
                errors.append(_(
                    "We were not able to find one of the VAT taxes for company %(company_name)s:"
                    "\n - 22% Sales VAT\n - 10% Sales VAT\n - Exempt Sales VAT", company_name=company.name))

        return errors

    def l10n_uy_edi_action_download_preview_xml(self):
        # EXTEND l10n_uy_edi
        """ En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.
        Aca extendemos para se pueda descargar en cualquier momento, Si no exsite el documento lo genera y lo descargar """
        if not self.l10n_uy_edi_document_id.attachment_id:
            xml_file = self._l10n_uy_edi_get_preview_xml()
            self.l10n_uy_cfe_xml = xml_file.datas

        return super().l10n_uy_edi_action_download_preview_xml()

    def _l10n_uy_edi_cfe_A_receptor(self):
        # EXTEND l10n_uy_edi
        """ Agregamos campos que existen en odoo modulo oficial y queremos enviar en el xml
        """
        res = super()._l10n_uy_edi_cfe_A_receptor()
        if self._is_uy_resguardo():
            res.pop("CompraID", False)
        return res

    def _l10n_uy_edi_cfe_C_totals(self, tax_details):
        # EXTEND l10n_uy_edi
        """ A130 Monto Total a Pagar (NO debe ser reportado si de tipo e-resguardo) """
        # TODO KZ mover esto a modulo e-resguardo una vez lo tengamos
        res = super()._l10n_uy_edi_cfe_A_receptor(tax_details)
        if self._is_uy_resguardo():
            res.pop("MntPagar")
        return res

    def l10n_uy_edi_action_update_dgi_state(self):
        # EXTEND l10n_uy_edi
        """ Extendemos boton para que funcione tanto para facturas de cliente como proveedor """

        # Customer Invoices
        sale_docs = self.filtered(lambda x: x.journal_id.type == "sale")
        super(AccountMove, sale_docs).l10n_uy_edi_action_update_dgi_state()

        # Vendor bills
        vendor_docs = self.filtered(lambda x: x.journal_id.type != "sale")
        for bill in vendor_docs:
            document_number = re.search(r"([A-Z]*)([0-9]*)", bill.l10n_latam_document_number).groups()
            result = bill.l10n_uy_edi_document_id._ucfe_inbox("650", {
                "TipoCfe": bill.l10n_latam_document_type_id_code,
                "Serie": document_number[0],
                "NumeroCfe": document_number[1],
                "RutEmisor": bill.partner_id.vat})

            response = result.get("response")
            if response is not None:
                if notif := response.findtext(".//{*}TipoNotificacion"):
                    bill.write({"l10n_uy_ucfe_notif": notif})
            bill.l10n_uy_edi_document_id._update_cfe_state(result)

    # New methods

    def uy_ux_action_get_uruware_cfe(self):
        """ Boton visible en diario manual que permite con el dato del UUID cargar la factura creada en
        Uruware postmorten en el Odoo (INBOX 360 - Consulta de estado de CFE).

        Los datos que sincroniza son

            * numero de documento
            * tipo de documento
            * estado del comprobante
        """
        # TODO KZ: Implementar approach odoo (generen un nuevo diario manual) y carguen ahi el documento
        #  2.1. hacer el campo uuid editable y stored en la factura, y que ahi pongan el valor que quieran
        #  2.2. approach de consultar el comprobante emitido con ws y descargar la info del xml y auto popular
        #    como hacemos con facturas proveedor
        # TODO Improve add logic:
        # 1. add information to the cfe xml
        # 2. cfe another data
        # 3. validation that is the same CFE

        uy_moves = self.filtered(
            lambda x: x.country_code == "UY" and x.journal_id.type == "sale"
            and x.journal_id.l10n_uy_edi_type == "electronic")
        uy_docs = self.env["l10n_latam.document.type"].search([("country_id.code", "=", "UY")])

        for move in uy_moves:

            if not move.l10n_uy_edi_cfe_uuid:
                raise UserError(_("Necesita definir 'Clave o UUID del CFE' para poder continuar"))

            move.l10n_uy_edi_document_id.unlink()
            edi_doc = move.l10n_uy_edi_document_id._create_document(move)
            move.l10n_uy_edi_document_id = edi_doc

            result = edi_doc._ucfe_inbox("360", {"Uuid": edi_doc.uuid})
            edi_doc._update_cfe_state(result)
            response = result.get("response")
            if response is not None:
                uy_doc_code = response.findtext(".//{*}TipoCfe")
                serie = response.findtext(".//{*}Serie")
                doc_number = response.findtext(".//{*}NumeroCfe")
                move.write({
                    "l10n_latam_document_number": serie + "%07d" % int(doc_number),
                    "l10n_latam_document_type_id": uy_docs.filtered(lambda x: x.code == uy_doc_code).id,
                })

    def uy_ux_action_uy_get_pdf(self):
        """ Permite volver a generar el PDF cuando no existe sea que hubo error
        porque no se creo o alguien lo borro sin querer """
        # TODO KZ revisar porque en si conviene que almacene tambien en el file.
        # no estoy segura si lo esta haciendo
        self.ensure_one()
        if not self.invoice_pdf_report_file:
            return super()._l10n_uy_edi_get_pdf()

    @api.depends("name")
    def _compute_l10n_latam_document_number(self):
        # EXTEND l10n_latam_invoice_document
        """En el metodo original en latam suponemos que el codigo del tipo de documento no tiene espacios.
        Y por ello conseguimos el numero haciendo el split al coseguir el primer espacio en blanco.

        En este caso los nombres de docs uruguayos a hoy en adhoc, tienen espacios. por eso necesitamos tomar otro
        criterio.

        Este metodo lo que hace es llamar el original y posterior corregir los documentos uruguayos para solo tomar
        realmente la ultima parte del name seria el numero en si.

        Sin este cambio, si el name es "ND e-Ticket 00000001" coloca el "e-Ticket 00000001" como numero de doc
        Con este cambio, si el name es "ND e-Ticket 00000001" coloca el "00000001" como numero de doc"""
        super(AccountMove, self)._compute_l10n_latam_document_number()
        uy_recs_with_name = self.filtered(lambda x: x.country_code == "UY" and x.name != "/")
        for rec in uy_recs_with_name:
            name = rec.l10n_latam_document_number
            doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
            if doc_code_prefix and name:
                name = name.split(" ")[-1]
            rec.l10n_latam_document_number = name

    # def _l10n_uy_edi_cfe_F_reference(self):
    #     # TODO KZ Not sure if FechaCFEref": 2015-01-31, shuould be inform

    # Nuevos metodos

    def action_l10n_uy_get_pdf(self):
        """ boton que permite descargar nuevamente el pdf de uruware y adjuntarlo a odoo """
        self.ensure_one()
        pdf_result = self._l10n_uy_edi_get_pdf()
        if pdf_file := pdf_result.get("pdf_file"):
            # make sure latest PDF shows to the right of the chatter
            pdf_file.register_as_main_attachment(force=True)
            self.invalidate_recordset(fnames=["invoice_pdf_report_id", "invoice_pdf_report_file"])
        if errors := pdf_result.get("errors"):
            msg = _("Error getting the PDF file: %s", errors)
            self.l10n_uy_edi_error = (self.l10n_uy_edi_error or "") + msg
            self.message_post(body=msg)

    def uy_ux_action_validate_cfe(self):
        """ Check CFE XML valid files: 350: Validación de estructura de CFE """
        self.ensure_one()

        self.l10n_uy_edi_document_id.unlink()
        edi_doc = self.l10n_uy_edi_document_id._create_document(self)
        self.l10n_uy_edi_document_id = edi_doc

        result = edi_doc._ucfe_inbox("350", {"CfeXmlOTexto": self.l10n_uy_cfe_xml})
        response = result.get("response")
        if response is not None:
            cod_rta = response.findtext(".//{*}CodRta")
            if cod_rta != "00":
                edi_doc._update_cfe_state(result)
                edi_doc.message = _("Error al crear el XML del CFẸ") + "\n\n" + edi_doc.message
                # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
                # response.Resp.MensajeRta
                self.l10n_uy_edi_error = _("Error al crear el XML del CFẸ\n\n %(errors)s", errors=response)

    def action_l10n_uy_remkark_default(self):
        self.ensure_one()
        res = self.env["l10n_uy_edi.addenda"]

        res |= self._uy_get_legends_recs("addenda", self)
        res |= self._uy_get_legends_recs("cfe_doc", self)
        res |= self._uy_get_legends_recs("emisor", self)
        res |= self._uy_get_legends_recs("receiver", self)

        for line in self._uy_get_cfe_lines():
            res |= self._uy_get_legends_recs("item", line)

        self.l10n_uy_edi_addenda_ids = res

    def action_l10n_uy_addenda_preview(self):
        self.ensure_one()
        raise UserError(self._uy_get_cfe_addenda())

    def action_l10n_uy_mandatory_legend(self):
        self.ensure_one()
        addenda = self._uy_get_cfe_addenda()
        A16_InfoAdicionalDoc = self._uy_cfe_A16_InfoAdicionalDoc().get("InfoAdicionalDoc")
        A51_InfoAdicionalEmisor = self._uy_cfe_A51_InfoAdicionalEmisor().get("InfoAdicionalEmisor")
        A68_InfoAdicionalReceptor = self._uy_cfe_A68_InfoAdicional().get("InfoAdicional")
        B8_DscItem = []
        lines = self._uy_get_cfe_lines()
        for line in lines:
            value = self._uy_cfe_B8_DscItem(line).get("DscItem")
            if value:
                B8_DscItem.append((line.display_name, value))

        messge = "* Adenda\n%s\n\n* Info Adicional Doc\n%s\n\n* Info Adicional Emisor\n%s\n\n* Info Adicional Receptor\n%s\n\n * Info Adicional Items\n%s" % (
            addenda, A16_InfoAdicionalDoc, A51_InfoAdicionalEmisor, A68_InfoAdicionalReceptor, "\n".join(str(item) for item in B8_DscItem))

        raise UserError(messge)

    def _uy_get_legends_recs(self, tipo_leyenda, record):
        """ copy of  _uy_get_legends but return browseables """
        res = self.env["l10n_uy_edi.addenda"]
        recordtype = {
            "account.move": "inv",
            "stock.picking": "picking",
            "account.move.line": "aml",
            "product.product": "product"
        }
        context = {recordtype.get(record._name): record}
        for rec in record.company_id.l10n_uy_edi_addenda_ids.filtered(lambda x: x.type == tipo_leyenda and x.apply_on in ["all", self._name]):
            if bool(safe_eval.safe_eval(rec.condition, context)):
                res |= rec
        return res

    @api.constrains("move_type", "journal_id")
    def _uy_ux_check_moves_use_documents(self):
        """ Do not let to create not invoices entries in journals that use documents """
        # TODO simil to _check_moves_use_documents. integrate somehow
        not_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == "UY" and x.journal_id.type in ["sale", "purchase"] and
            x.l10n_latam_use_documents and not x.is_invoice())
        if not_invoices:
            raise ValidationError(_(
                "The selected Journal can't be used in this transaction, please select one that doesn't use documents"
                " as these are just for Invoices."))

    # TODO KZ esto lo usabamos para el tema de calcular autoamticamente las addendas, pero
    # no parece estar siendo usando, revisar si podemos borrar
    @api.model
    def is_zona_franca(self):
        """ NOTE: Need to improve the way to identify the fiscal position """
        return bool(self.fiscal_position_id and "zona franca" in self.fiscal_position_id.name.lower())

    # TODO KZ esto era necesario en AR para eliminar facturas de proveedor, revisar si sigue siendo ver de agregar
    # o eliminar
    # def unlink(self):
    #     """ When using documents on vendor bills the document_number is set manually by the number given from the
    #     vendor so the odoo sequence is not used. In this case we allow to delete vendor bills with
    #     document_number/name """
    #     self.filtered(lambda x: x.move_type in x.get_purchase_types() and x.state in ("draft", "cancel") and
    #                   x.l10n_latam_use_documents).write({"name": "/"})
    #     return super().unlink()

    # TODO KZ esto lo tendriamos que mantener para nuestros clientes que tiene el nombre largo como prefijo de
    # documento. capaz lo mejor seria hacer un script para poner todo como hace Odoo. Si hacemos eso este metodo se va

    # def _uy_cfe_A41_RznSoc(self):
    # TODO company register name?

    # Methods for vendor bills functionality

    def action_l10n_uy_update_fields(self):
        """ Sync with Uruware and complete vendor bill information. """
        self.ensure_one()
        self.clear_l10n_uy_invoice_fields()
        xml_string = self.l10n_uy_edi_xml_attachment_id.datas

        root = ET.fromstring(xml_string)
        self.l10n_uy_complete_invoice_with_xml(self.company_id, root, self)

    def clear_l10n_uy_invoice_fields(self):
        """ When click the button "Update fields" in the vendor bill form view, firstly is neccessary to clean the
        invoices lines, the partner, the invoices date due and the payment type and if there is an error then is posted
        the message of the error in the invoice chatter.  """
        error = False
        try:
            self = self.filtered(lambda x: x.invoice_filter_type_domain == "purchase").with_context(dynamic_unlink=True)
            self.line_ids.unlink()
            self.partner_id = False
            self.invoice_date_due = False
            self.l10n_uy_payment_type = False
        except Exception as exp:
            error = exp
            self.env.cr.rollback()
        if error:
            msg = _("We found an error when cleaning the information from the invoice: id: %s." % (str(error)))
            _logger.warning(msg)
            self.message_post(body=msg)

    def cron_l10n_uy_get_vendor_bills(self):
        """UY: Create vendor bills (sync from Uruware)"""
        self.l10n_uy_get_l10n_uy_received_bills()

    def l10n_uy_complete_invoice_with_xml(self, company, root, invoice):
        """ Here is completed the invoice with the information from the xml. """
        error = False
        invoice_date_due = False
        try:
            partner_vat_RUC = root.findtext(".//RUCEmisor")
            l10n_latam_document_number = root.findtext(".//Serie") + root.findtext(".//Nro").zfill(7)
            date_format = "%Y-%m-%d"
            invoice_date = datetime.strptime(root.findtext(".//FchEmis"), date_format).date()
            fecha_vto = root.findtext(".//FchVenc")
            if fecha_vto:
                invoice_date_due = datetime.strptime(fecha_vto, date_format).date()
            fma_pago = root.findtext(".//FmaPago")
            if fma_pago and fma_pago == "2":
                invoice.l10n_uy_payment_type = "credit"
            invoice_currency = root.findtext(".//TpoMoneda")
            cant_lineas = root.findtext(".//CantLinDet")
            partner_id = self.env["res.partner"].search([("commercial_partner_id.vat", "=", partner_vat_RUC)], limit=1)
            # Si no existe el partner lo creamos
            if not partner_id:
                partner_id = self.l10n_uy_create_partner_from_notification(root, partner_vat_RUC)
            # Voy guardando de a un campo porque en ciertos casos de borran, ver si se puede mejorar
            invoice.invoice_date = invoice_date
            invoice.partner_id = partner_id.id
            currency_id = self.env["res.currency"].search([("name", "=", invoice_currency)])
            if not currency_id:
                currency_id = self.env["res.currency"].with_context(active_test=False).search(
                    [("name", "=", invoice_currency)])
                if currency_id:
                    error = _("The currency %s is not Active. Please active it to continue." % (invoice_currency))
                else:
                    error = _("The currency %s does not exists in Odoo." % (invoice_currency))
            else:
                invoice.currency_id = currency_id.id
                # Process Invoice Lines. To iterate is used findall.
                invoice_line_ids = root.findall(".//Item")
                line_ids = self.l10n_uy_vendor_prepare_lines(company, invoice_line_ids, invoice)
                invoice.line_ids = line_ids
                if len(invoice.invoice_line_ids) != int(cant_lineas):
                    error = _("The number of invoice lines %s (id:%d) is invalid") % (invoice.name, invoice.id)
            if invoice_date_due:
                invoice.invoice_date_due = invoice_date_due
            invoice.l10n_latam_document_type_id = self.l10n_uy_get_cfe_document_type(root).id
            invoice.l10n_latam_document_number = l10n_latam_document_number
            self.env.cr.commit()
            invoice_amount_total = invoice.amount_total
            xml_amount_total = float(root.findtext(".//MntPagar"))
            if float_compare(invoice_amount_total, xml_amount_total,
                             precision_digits=invoice.currency_id.decimal_places):
                invoice.message_post(
                    body=_("There is a difference between the invoice total amount in Odoo and the invoice XML. "
                           "Odoo: %.2f  XML: %.2f . <strong>Warning:</strong> The total amount of the XML is %s "
                           "and the total amount calculated by Odoo is %s. Typically this is caused by additional "
                           "lines in the detail or by unidentified taxes or by rounding method configuration or by "
                           "invoices with tax included, please check if a manual correction is needed.")
                    % (invoice_amount_total,
                       xml_amount_total,
                       formatLang(self.env, xml_amount_total, currency_obj=invoice.currency_id),
                       formatLang(self.env, invoice_amount_total, currency_obj=invoice.currency_id)))
        except Exception as exp:
            error = str(exp)
        if error:
            self.env.cr.rollback()
            message = _("We found an error when loading information in this invoice %s (id: %d) %s" % (
                invoice.name, invoice.id, error))
            invoice.message_post(body=message)
            _logger.warning(message)

    def l10n_uy_create_cfe_from_xml(self, company, root, l10n_uy_idreq, response_610, journal):
        """ Here the vendor bills are created and synchronized through the Uruware notification request. """
        doc = self.l10n_uy_get_cfe_document_type(root)
        move_type = doc._get_move_type()
        xml_string = self.l10n_uy_get_parsed_xml_cfe(response_610, l10n_uy_idreq)
        # TOOD KZ Create xml attachment?
        move = self.env["account.move"].create({
            "l10n_uy_idreq": l10n_uy_idreq,
            "move_type": move_type,
            "l10n_uy_cfe_xml": xml_string,
            "l10n_latam_document_type_id": doc.id,
            "journal_id": journal.id,
        })
        edi_doc = move.l10n_uy_edi_document_id._create_document(move)
        move.l10n_uy_edi_document_id = edi_doc

        move._update_l10n_uy_edi_cfe_state()
        partner_vat_RUC = root.findtext(".//RUCEmisor")
        serieCfe = root.findtext(".//Serie")
        l10n_latam_document_number = root.findtext(".//Nro")

        req_data_pdf = {"rut": company.vat,
                        "rutRecibido": partner_vat_RUC,
                        "tipoCfe": move.l10n_latam_document_type_id.code,
                        "serieCfe": serieCfe,
                        "numeroCfe": l10n_latam_document_number}

        l10n_uy_cfe_file = self.env["ir.attachment"].create({
            "name": "CFE_{}.xml".format(serieCfe + l10n_latam_document_number.zfill(7)),
            "res_model": self._name, "res_id": move.id,
            "type": "binary", "datas": base64.b64encode(xml_string)}).id
        move.l10n_uy_cfe_file = l10n_uy_cfe_file
        self.l10n_uy_create_pdf_vendor_bill(company, move, req_data_pdf)
        self.env.cr.commit()
        self.l10n_uy_complete_invoice_with_xml(company, root, move)

    def l10n_uy_create_partner_from_notification(self, root, partner_vat_RUC):
        """ In case we need to create vendor bills synchronized with Uruware through notifications and the
        partner from the bill does not exist id Odoo, then we create it in this method. """
        partner_name = root.findtext(".//RznSoc")
        partner_city = root.findtext(".//Ciudad")
        partner_state_id = root.findtext(".//Departamento")
        partner_street = root.findtext(".//DomFiscal")
        state_id = self.env["res.country.state"].search([("name", "ilike", partner_state_id)], limit=1)
        country_id = state_id.country_id
        ruc = self.env.ref("l10n_uy_account.it_rut").id
        partner_vals = {"name": partner_name,
                        "vat": partner_vat_RUC,
                        "city": partner_city,
                        "street": partner_street,
                        "state_id": state_id.id,
                        "country_id": country_id.id,
                        "l10n_latam_identification_type_id": ruc,
                        "is_company": True}
        partner_id = self.env["res.partner"].create(partner_vals)
        return partner_id

    def l10n_uy_create_pdf_vendor_bill(self, invoice, req_data_pdf):
        """ The vendor bill pdf is created and syncronized through the Uruware notification request. """
        response_reporte_pdf = self.l10n_uy_edi_document_id._ucfe_query("ObtenerPdfCfeRecibido", req_data_pdf)
        invoice.invoice_pdf_report_id = self.env["ir.attachment"].create({
            "name": (
                invoice.l10n_latam_document_type_id.doc_code_prefix + " "
                + req_data_pdf.get("serieCfe")
                + req_data_pdf.get("numeroCfe").zfill(7)).replace("/", "_") + ".pdf",
            "res_model": invoice._name, "res_id": invoice.id,
            "type": "binary", "datas": base64.b64encode(response_reporte_pdf)
        })

    def l10n_uy_get_cfe_document_type(self, root):
        """ :return: latam document type in Odoo that represented the XML CFE. """
        l10n_latam_document_type_id = root.findtext(".//TipoCFE")
        return self.env["l10n_latam.document.type"].search([("code", "=", l10n_latam_document_type_id),
                                                            ("country_id.code", "=", "UY")])

    def l10n_uy_get_l10n_uy_received_bills(self):
        """ UY: Create vendor bills from Uruware. If there are notifications available on Uruware side then here
        is pulled that information, then we create the vendor bill and after that we dismiss the notification to
        continue reading the netx one until there are no more notifications available. """
        # TODO test it
        # 600 - Consulta de Notificacion Disponible
        edi_doc = self.env["l10n_uy_edi.document"]
        for journal in self.env["account.journal"].search([
                ("type", "=", "purchase"),
                ("l10n_uy_edi_type", "=", "electronic"),
                ("country_code","=", "UY"),
                ("company_id.l10n_uy_ucfe_get_vendor_bills", "=", True)]):
            company = journal.company_id
            band = True
            # If there is notifications
            while band:
                try:
                    # response.Resp.TipoNotificacion
                    # 610 - Solicitud de datos de Notificacion
                    response_600 = self.l10n_uy_notification_consult(company)
                    # Si guardo idReq de la solicitud 600 luego más adelante puedo volver a consultar la notificación
                    # y no hace falta descartarla
                    # Por lo tanto conviene guardar el idReq y adjuntarlo a la factura
                    if not self.l10n_uy_notification_verify_codrta(company, response_600):
                        band = False
                        break
                    l10n_uy_idreq = response_600.Resp.IdReq
                    response_610 = edi_doc._ucfe_inbox("610", {"IdReq": l10n_uy_idreq})
                    root = self.l10n_uy_vendor_create_xml_root(response_610, l10n_uy_idreq)
                except:
                    _logger.warning("Encontramos un error al momento de sincronizar comprobantes de proveedor de la compañía: %s (id: %d)" % (company.name, company.id))
                    band = False
                    break
                # Check if internal_type is not purchase
                # Only implemented for vendor bills and vendor refunds
                if "in_" in self.l10n_uy_get_cfe_document_type(root)._get_move_type():
                    self.l10n_uy_create_cfe_from_xml(company, root, l10n_uy_idreq, response_610, journal)
                self.l10n_uy_notification_dismiss(company, response_600)

    def l10n_uy_get_parsed_xml_cfe(self, response_610, l10n_uy_idreq):
        xml_string = response_610.Resp.XmlCfeFirmado
        if not xml_string:
            raise UserError(_("There is no information to create the vendor bill in the notification %d consulted") % (l10n_uy_idreq))
        return self.l10n_uy_vendor_prepare_cfe_xml(xml_string)

    def _l10n_uy_get_tax_not_implemented_description(self, ind_fact):
        """ There are some taxes no implemented for Uruguay, so when move lines are created and if those ones don`t have ind_fact (Indicador de facturación) 1, 2 or 3 then is concatenated the name of the tax not implemented with the name of the line.  """
        data = {
            "1": "Exento de IVA",
            "2": "Gravado a Tasa Mínima",
            "3": "Gravado a Tasa Básica",
            "4": "Gravado a Otra Tasa/IVA sobre fictos",
            "5": "Entrega gratuita",
            "6": "No facturable",
            "7": "No facturable negativo",
            "8": "Ítem a rebajar en e-remitos",  # Solo e-remitos
            "9": "Ítem a anular en resguardos",  # Solo e-resguardos
            "10": "Exportación y asim",
            "11": "Impuesto percibido",
            "12": "IVA en suspenso",

            # Sólo para e-Boleta de entrada
            "13": "Ítem vendido por un no contribuyente",
            "14": "Ítem vendido por un contribuyente IVA mínimo, Monotributo o Monotributo MIDES",
            "15": "Ítem vendido por un contribuyente IMEBA",
            "16": "Sólo para ítems vendidos por contribuyentes con obligación IVA mínimo, Monotributo o Monotributo MIDES",
        }

        res = data.get(ind_fact, "INDICADOR NO CONICIDO %s" % ind_fact)
        if not res:
            _logger.warning(_("IndFact no implementado en Odoo %s"), ind_fact)
        return res

    def l10n_uy_notification_consult(self, company=False):
        """ 600 - Consult notifications available. """
        company = company or self.env.company

        # TODO KZ need to update to take into account the current move instead of company
        edi_doc = self.env["l10n_uy_edi.document"]
        response = edi_doc._ucfe_inbox("600", {"TipoNotificacion": "7"})
        # .. here do anything needed to process errors etc
        return response

    def l10n_uy_notification_dismiss(self, company, response):
        """ This is implemented for vendor bills. Is needed to dismiss the last notification if the last vendor bill was created in Odoo from Uruware. To dismiss the last notification is needed to use the operation "620 - Descartar una notificación" with IdReq and TipoNotificacion. If is not possible to dismiss the last notification it will be returned the code "00" """
        error = False
        try:
            # TODO KZ need to update to take into account the current move instead of company
            edi_doc = self.env["l10n_uy_edi.document"]
            # response3 = company._ucfe_inbox("620", {
            response3 = edi_doc._ucfe_inbox("620", {
                "IdReq": response.Resp.IdReq,
                "TipoNotificacion": response.Resp.TipoNotificacion})
            if response3.Resp.CodRta != "00":
                error = _("ERROR: the notification could not be dismissed %s") % response
        except Exception as exp:
            error = exp
            self.env.cr.rollback()
        if error:
            _logger.warning(_("We found an error when dismissing the notification: id: %s . Error: %s" % (response.Resp.IdReq, str(error))))

    def l10n_uy_notification_verify_codrta(self, company, response):
        """ Verify response code from notifications (vendor bills). If response code is != 0 return True (can`t create new vendor bill), else return False (continue the process and create vendor bill).
        Available values for response code:
        00 Petición aceptada y procesada.
        01 Petición denegada.
        03 Comercio inválido.
        05 CFE rechazado por DGI.
        06 CFE observado por DGI.
        11 CFE aceptado por UCFE, en espera de respuesta de DGI.
        12 Requerimiento inválido.
        30 Error en formato.
        31 Error en formato de CFE.
        89 Terminal inválida.
        96 Error en sistema.
        99 Sesión no iniciada.
        ? Cualquier otro código no especificado debe entenderse como
        requerimiento denegado."""
        cod_rta = response.Resp.CodRta
        if cod_rta == "01":
            return False
        elif cod_rta != "00":
            _logger.info(_("ERROR: This is what we receive when requesting notification data (610) %s") % response)
            return False
        else:
            return True

    def l10n_uy_vendor_create_xml_root(self, response_610, l10n_uy_idreq):
        """ Create root tree that is used to read the tags from the xml received. """
        xml_string = self.l10n_uy_get_parsed_xml_cfe(response_610, l10n_uy_idreq)
        root = ET.fromstring(xml_string)
        return root

    def l10n_uy_vendor_prepare_cfe_xml(self, xml_string):
        """ Parse cfe xml so enable to create vendor bills. We don´t know which format of xml is received, so it is needed to clean the tags of the xml to make it readable by the library xml.etree.ElementTree .  """
        xml_string = xml_string.replace("ns0:", "").replace("nsAd:", "").replace("nsAdenda:", "")
        xml_string = re.sub(r"<eFact[^>]*>", "<eFact>", xml_string)
        return re.sub(r"<CFE[^>]*>", "<CFE>", xml_string)

    def l10n_uy_vendor_prepare_lines(self, company, invoice_line_ids, invoice):
        """ Here are prepared the lines of vendor bills that are synchronized through the Uruware notification request. """
        line_ids = []
        for value in invoice_line_ids:
            domain_tax = [("country_code", "=", "UY"), ("company_id", "=", company.id), ("type_tax_use", "=", "purchase")]
            ind_fact = value.findtext(".//IndFact")
            if ind_fact == "1":
                # Exento de IVA
                domain_tax += [("tax_group_id.l10n_uy_vat_code", "=", "vat_exempt")]
            elif ind_fact == "2":
                # Gravado a Tasa Mínima
                domain_tax += [("tax_group_id.l10n_uy_vat_code", "=", "vat_10")]
            elif ind_fact == "3":
                # Gravado a Tasa Básica
                domain_tax += [("tax_group_id.l10n_uy_vat_code", "=", "vat_22")]
            price_unit = value.findtext(".//PrecioUnitario")
            tax_item = self.env["account.tax"].search(domain_tax, limit=1)
            line_vals = {
                "move_type": invoice.l10n_latam_document_type_id._get_move_type(),
                # There are some taxes no implemented for Uruguay, so when move lines are created and if those ones have ind_fact not in 1, 2 or 3 then is concatenated the name of the tax not implemented with the name of the line.
                "name": value.findtext(".//NomItem") + (" (*%s)" % self._l10n_uy_get_tax_not_implemented_description(ind_fact) if ind_fact not in ["1", "2", "3"] else ""),
                "quantity": float(value.findtext(".//Cantidad")),
                "price_unit": float(price_unit) if ind_fact != "7" else -1*float(price_unit),
                "tax_ids": [(6, 0, tax_item.ids)] if ind_fact in ["1", "2", "3"] else []}
            line_ids.append((0, 0, line_vals))
        return line_ids
