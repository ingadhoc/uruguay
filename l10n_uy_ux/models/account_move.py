import base64
import logging

from lxml import etree
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_latam_document_type_id = fields.Many2one(change_default=True)
    # This is needed to be able to save default values
    # TODO KZ hacer pr a 17 o master pidiendo que hagan este fix directamtne
    # en el modulo de l10n_latam_invoice_document

    l10n_uy_cfe_xml = fields.Text("Technical field to preview the xml")
    manual_uruware_invoice = fields.Char()

    # EXTENDS

    def _l10n_uy_edi_check_move(self):
        # EXTEND l10n_uy_edi
        """Validaciones previas a enviar a DGI que Odoo no nos acepto

        - Que el diario este bien configurado antes de emitir
        - Que las momendas esten bien configuradas
        - Que los impuestos IVA 0 10 y 22 existan en la companñia
        """
        errors = super()._l10n_uy_edi_check_move()

        # TODO KZ estaria bueno revisar que este acitva UYI? self.env.ref('base.UYI').active
        if not self.company_id.currency_id:
            errors.append(self.env._("You need to configure the company currency"))

        if self.journal_id.type == "sale" and self.journal_id.l10n_uy_edi_type not in [
            "electronic",
            "manual",
        ]:
            errors.append(self.env._("Missing uruguayan invoicing type on journal %s.", self.name))

        # # VAT Configuration
        # for company in self.company_id:
        #     taxes = self.env["account.tax"].search([("company_id", "=", company.id), ("l10n_uy_tax_category", "=", "vat")])
        #     tax_22 = taxes.filtered(lambda x: x.amount == 22)
        #     tax_10 = taxes.filtered(lambda x: x.amount == 10)
        #     tax_0 = taxes.filtered(lambda x: x.amount == 0)
        #     if not tax_22 or not tax_10 or not tax_0:
        #         errors.append(self.env._(
        #             "We were not able to find one of the VAT taxes for company %(company_name)s:"
        #             "\n - 22% Sales VAT\n - 10% Sales VAT\n - Exempt Sales VAT", company_name=company.name))

        return errors

    def _l10n_uy_edi_send(self):
        """Antes de enviar a DGI, corremos los chequeos previos para atrapar algunos errores conocidos y de fácil configuración.
        Si obtenemos alguno, no continuamos con el envío a DGI y en cambio creamos el XML con el error."""
        moves_to_send = self
        for move in self:
            move.l10n_uy_edi_document_id.filtered(lambda doc: doc.state == "error").unlink()
            edi_doc = self.env["l10n_uy_edi.document"].create(
                {
                    "move_id": move.id,
                    "uuid": self.env["l10n_uy_edi.document"]._get_uuid(move),
                }
            )
            move.l10n_uy_edi_document_id = edi_doc
            if pre_checks_errors := move._l10n_uy_edi_check_move():
                edi_doc.message = self.env._("Errors occurred while evaluating the document: \n") + "\n *".join(
                    pre_checks_errors
                )
                edi_doc.state = "error"
                moves_to_send -= move

        super(AccountMove, moves_to_send)._l10n_uy_edi_send()

    def _post(self, soft=True):
        """Extendemos el _post nativo para evitar hacer la confirmación en dos pasos con el wizard de Send & Print.
        De esta manera, al clickear en confirmar las facturas automáticamente serán enviadas a DGI y posteadas.
        En caso de error, se vuelven a estado borrador.
        """
        # EXTENDS l10n_uy_edi
        res = super()._post(soft=soft)
        if self.env.context.get("l10n_uy_skip_edi_send"):
            return res
        msg = self.env._("Error trying to validate the document in DGI")
        for move in res.filtered(lambda m: m.l10n_uy_edi_is_needed):
            move._l10n_uy_edi_send()
            if move.l10n_uy_edi_error:
                error_msg = Markup("<font style='color:Tomato;'><strong>ERROR:</strong></font> <i>{}</i>").format(
                    f"{msg}: {move.l10n_uy_edi_error}"
                )
                move.message_post(body=error_msg, body_is_html=True)
                move.button_draft()
                res = res - move
        return res

    def action_send_invoice_mail(self):
        """Extendemos método de account_ux para que en las facturas uruguayas se adjunten los archivos en el envío de mail."""
        if (
            self.env["ir.module.module"]
            .sudo()
            .search(
                [
                    ("name", "=", "account_ux"),
                    ("state", "in", ["installed", "to upgrade"]),
                ]
            )
        ):
            uy_edi_moves = self.filtered(lambda m: m.journal_id.l10n_uy_edi_type == "electronic")
            super(AccountMove, self - uy_edi_moves).action_send_invoice_mail()

            for move in uy_edi_moves.filtered(lambda x: x.journal_id.mail_template_id):
                if move.partner_id.email:
                    try:
                        wizard = self.env["account.move.send.wizard"].sudo().create({"move_id": move.id})
                        wizard.sudo().action_send_and_print()
                    except Exception as error:
                        title = _("ERROR: Invoice was not sent via email")
                        move.message_post(
                            body="<br/><br/>".join(
                                [
                                    "<b>" + title + "</b>",
                                    _("Please check the email template associated with the invoice journal."),
                                    "<code>" + str(error) + "</code>",
                                ]
                            ),
                            body_is_html=True,
                        )
                else:
                    move.message_post(
                        body=_(
                            "<b>Error sending the invoice</b>: partner %s does not have an email address defined.",
                            move.partner_id.name,
                        ),
                        body_is_html=True,
                    )

    def action_switch_move_type(self):
        if self:
            in_out, old_move_type = self[0].move_type.split("_")
            new_move_type = f"{in_out}_{'invoice' if old_move_type == 'refund' else 'refund'}"

            return super(AccountMove, self.with_context(switch_move_type=new_move_type)).action_switch_move_type()
        super().action_switch_move_type()

    @api.depends("l10n_latam_available_document_type_ids", "move_type")
    def _compute_l10n_latam_document_type(self):
        # EXTEND l10n_uy_edi
        """
        The following considerations apply for determining document types based on the partner's identification:
        RUT/RUC (Uruguay): Automatically select e-factura, e-credit note or e-debit note depending on the origin.
        Other documents (Example: CI, PAS, NIE, NIFE, etc.): Automatically select e-ticket
        """
        uy_cn_dn_docs = self.env["account.move"]
        if uy_einvoices := self.filtered(
            lambda m: (
                m.country_code == "UY"
                and m.move_type in ("out_invoice", "out_refund")
                and m.state == "draft"
                and not m.posted_before
                and m.journal_id.l10n_uy_edi_type == "electronic"
                and m.partner_id.l10n_latam_identification_type_id == self.env.ref("l10n_uy.it_rut")
            )
        ):
            # Set debit notes
            if uy_debit_notes := uy_einvoices.filtered(lambda m: m.debit_origin_id):
                uy_debit_notes.l10n_latam_document_type_id = self.env.ref("l10n_uy.dc_dn_e_inv")
                uy_cn_dn_docs |= uy_debit_notes

            # Set credit notes
            new_move_type = self.env.context.get("switch_move_type")
            uy_credit_notes = uy_einvoices.filtered(lambda m: m.reversed_entry_id or "refund" in m.move_type)
            if new_move_type and "refund" in new_move_type:
                uy_credit_notes |= uy_einvoices.filtered(lambda m: not m.reversed_entry_id)
            if uy_credit_notes:
                uy_credit_notes.l10n_latam_document_type_id = self.env.ref("l10n_uy.dc_cn_e_inv")
                uy_cn_dn_docs |= uy_credit_notes

        super(AccountMove, self - uy_cn_dn_docs)._compute_l10n_latam_document_type()

    # New methods

    def uy_ux_action_preview_xml(self):
        """En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.

        Este es un nuevo boton preview que permite pre visualizar el contenido del xml en cualquier momento, incluso
        cuando la factura aun esta en estado borrador.

        NOTA: Para que pueda funcionar necesitamos tener definido la fecha de factura porque sino el xml falla, por eso
        en este metodo temporalmente asignamos la fecha de factura a la de hoy y luego la borramos para que quede la
        factura tal cual estaba"""
        not_invoice_date = not self.invoice_date
        if not_invoice_date:
            self.invoice_date = fields.Date.today()
        self.l10n_uy_cfe_xml = self._l10n_uy_edi_get_xml_content().encode()
        if not_invoice_date:
            self.invoice_date = False

    def uy_ux_action_get_uruware_cfe(self):
        """Boton visible en diario manual que permite con el dato del UUID cargar la factura creada en
        Uruware postmorten en el Odoo

        (INBOX 360 - Consulta de estado de CFE).

        Los datos que sincroniza son

            * numero de documento
            * tipo de documento
            * estado del comprobante
            - crea el EDI document
            - agregar el pdf de la factura
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
            lambda x: (
                x.country_code == "UY" and x.journal_id.type == "sale" and x.journal_id.l10n_uy_edi_type == "manual"
            )
        )
        uy_docs = self.env["l10n_latam.document.type"].search([("country_id.code", "=", "UY")])

        for move in uy_moves:
            if not move.manual_uruware_invoice:
                raise UserError(self.env._("You need to define 'CFE Key or UUID' in order to continue"))
            edi_doc = self.env["l10n_uy_edi.document"].create(
                {
                    "move_id": move.id,
                    "uuid": self.manual_uruware_invoice,
                }
            )
            move.l10n_uy_edi_document_id = edi_doc
            result = edi_doc._ucfe_inbox("360", {"Uuid": edi_doc.uuid})
            edi_doc._update_cfe_state(result)
            response = result.get("response")
            if response is not None:
                uy_doc_code = response.findtext(".//{*}TipoCfe")
                serie = response.findtext(".//{*}Serie")
                doc_number = response.findtext(".//{*}NumeroCfe")
                if not serie or not doc_number:
                    raise UserError(
                        self.env._(
                            "No CFE was found in Uruware for the key '%s'. Please check that the"
                            " 'Uruware UUID' field contains the CFE key assigned in Uruware"
                            " (for documents issued from Odoo it looks like 'account.move-12345'),"
                            " not the document number.",
                            move.manual_uruware_invoice,
                        )
                    )
                move.write(
                    {
                        "l10n_latam_document_number": serie + "%07d" % int(doc_number),
                        "l10n_latam_document_type_id": uy_docs.filtered(lambda x: x.code == uy_doc_code).id,
                    }
                )
                move.uy_ux_action_uy_get_pdf()

    def uy_ux_action_uy_get_pdf(self):
        """Permite volver a generar el PDF cuando no existe, sea que hubo error
        porque no se creo o alguien lo borro sin querer"""
        # TODO KZ revisar porque en si conviene que almacene tambien en el file.
        # no estoy segura si lo esta haciendo
        self.ensure_one()
        if not self.invoice_pdf_report_file:
            res = {}
            result = self.l10n_uy_edi_document_id._get_pdf()

            if file_content := result.get("file_content"):
                pdf_file = self.env["ir.attachment"].create(
                    {
                        "res_model": "account.move",
                        "res_id": self.id,
                        "res_field": "invoice_pdf_report_file",
                        "name": (self.name or self.env._("INV")).replace("/", "_") + ".pdf",
                        "type": "binary",
                        "datas": file_content,
                    }
                )
                res["pdf_file"] = pdf_file

            return res

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

    def _l10n_uy_edi_get_line_nom_and_desc(self, aml):
        """
        Sobrescribimos este método que devuelve el valor de NomItem y DscItem para cada línea del comprobante...

        NomItem (B7) tiene un máximo de 80 caracteres y el resto se traslada a DscItem (B8). Para no cortar la
        última palabra en dos (una parte en NomItem y otra en DscItem), si el límite de 80 caracteres cae dentro
        de una palabra, esa palabra se traslada completa a la descripción. NomItem queda con longitud <= 80.
        """
        # B7 NomItem, B8 DscItem
        # Limpiamos saltos de línea que pueden romper el PDF
        clean_name = aml.name.replace("\n", " ").replace("\r", " ") if aml.name else ""

        max_len = 80
        if len(clean_name) <= max_len:
            nom_item = clean_name
            description = ""
        else:
            cut = max_len
            # Si el corte cae dentro de una palabra (el caracter límite no es un espacio), retrocedemos hasta el
            # último espacio para trasladar la palabra completa a la descripción.
            if not clean_name[max_len].isspace():
                last_space = clean_name.rfind(" ", 0, max_len)
                if last_space != -1:
                    cut = last_space + 1
            nom_item = clean_name[:cut]
            description = clean_name[cut:]

        nom_item = nom_item or "-"

        if aml.l10n_uy_edi_addenda_ids:
            adenda = [
                " {%s}" % addenda.content if addenda.is_legend else " " + addenda.content
                for addenda in aml.l10n_uy_edi_addenda_ids
            ]
            description += "".join(adenda)

        return nom_item, description

    # Nuevos metodos

    def action_l10n_uy_get_pdf(self):
        """boton que permite descargar nuevamente el pdf de uruware y adjuntarlo a odoo"""
        self.ensure_one()

        # Si estamos intentado forzar el volver a crear el PDF y estamos en ambiente DEMO simplemente generamos
        # el reporte no legal (asi no intenta conectarse a Uruware y salta error)
        if self.company_id.l10n_uy_edi_ucfe_env == "demo":
            self.env["account.move.send.wizard"].create({"move_id": self.id}).action_send_and_print()
            pdf_result = {
                "pdf_file": self.env["ir.attachment"].search(
                    [
                        ("res_model", "=", "account.move"),
                        ("res_id", "=", self.id),
                        ("res_field", "=", "invoice_pdf_report_file"),
                    ]
                )
            }
        else:
            pdf_result = self._l10n_uy_edi_get_pdf()

        if pdf_file := pdf_result.get("pdf_file"):
            # make sure latest PDF shows to the right of the chatter
            pdf_file.register_as_main_attachment(force=True)
            self.invalidate_recordset(fnames=["invoice_pdf_report_id", "invoice_pdf_report_file"])
        if errors := pdf_result.get("errors"):
            msg = self.env._("Error getting the PDF file: %s", errors)
            self.l10n_uy_edi_error = (self.l10n_uy_edi_error or "") + msg
            self.message_post(body=msg)

    def uy_ux_action_validate_cfe(self):
        """Check CFE XML valid files: 350: Validación de estructura de CFE

        To make the validation of the CFE and connect to uwaure we need to have a EDI document
        For that reason if we have one we delete it and create a new one with the result of
        the validation, since we are raising and the end of the method then the edi document
        is rolled back"""
        self.ensure_one()

        self.l10n_uy_edi_document_id.unlink()
        edi_doc = self.env["l10n_uy_edi.document"].create(
            {
                "move_id": self.id,
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
                edi_doc.message = self.env._("Error creating CFẸ XML") + "<br/><br/>" + edi_doc.message
                # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
                raise UserError(
                    self.env._(
                        "Error creating CFE XML\n\n %(errors)s",
                        errors=response.findtext(".//{*}MensajeRta"),
                    )
                )

        raise UserError(self.env._("Valid XML"))

    def action_l10n_uy_remkark_default(self):
        """Revisamos leyendas que correspondan aplicar segun las condiciones de leyenda y defaults y las agregamos a
        la factura y a las líneas con un boton"""
        self.ensure_one()

        # 1. Obtenemos las leyendas obligatorias
        default_legends = self.env["l10n_uy_edi.addenda"]
        default_legends |= self._uy_get_legends_recs("addenda", self)
        default_legends |= self._uy_get_legends_recs("cfe_doc", self)
        default_legends |= self._uy_get_legends_recs("emisor", self)
        default_legends |= self._uy_get_legends_recs("receiver", self)

        # Escribimos las leyendas en el move
        self.l10n_uy_edi_addenda_ids = default_legends

        # 2. Obtenemos y aplicamos las leyendas de tipo "item" a cada línea
        for line in self.invoice_line_ids.filtered(lambda x: x.display_type == "product"):
            # Obtenemos las de tipo item evaluando el contexto según la línea y según el move
            item_legends = self._uy_get_legends_recs("item", line)
            # Escribimos explícitamente en el account.move.line
            line.l10n_uy_edi_addenda_ids = item_legends

    def action_l10n_uy_addenda_preview(self):
        """Boton que permite previsualizar las addendas que seran aplicadas en en este comprobante"""
        self.ensure_one()
        raise UserError(self._l10n_uy_edi_get_addenda())

    def uy_ux_action_mandatory_legend(self):
        """Return Pop up with the preview of the mandatory legends that will be inform"""
        self.ensure_one()
        addenda = self._l10n_uy_edi_get_addenda()
        edi_model = self.env["l10n_uy_edi.document"]
        A16_InfoAdicionalDoc = edi_model._get_legends("cfe_doc", self)
        A51_InfoAdicionalEmisor = edi_model._get_legends("issuer", self)
        A68_InfoAdicionalReceptor = edi_model._get_legends("receiver", self)
        B8_DscItem = []
        for line in self.invoice_line_ids.filtered(lambda x: x.display_type == "product"):
            value = self._l10n_uy_edi_get_line_nom_and_desc(line)[1]
            if value:
                B8_DscItem.append("* line (%s) : %s" % (line.display_name, value))

        messge = _(
            "* Addenda\n%(addenda)s\n\n"
            "* Additional Doc Info\n%(doc_info)s\n\n"
            "* Additional Issuer Info\n%(issuer_info)s\n\n"
            "* Additional Receiver Info\n%(receiver_info)s\n\n"
            "* Additional Items Info\n%(items)s",
            addenda=addenda,
            doc_info=A16_InfoAdicionalDoc,
            issuer_info=A51_InfoAdicionalEmisor,
            receiver_info=A68_InfoAdicionalReceptor,
            items="\n".join(str(item) for item in B8_DscItem),
        )

        raise UserError(messge)

    def _uy_get_legends_recs(self, tipo_leyenda, record):
        """copy of  _uy_get_legends but return browseables"""
        res = self.env["l10n_uy_edi.addenda"]
        recordtype = {
            "account.move": "inv",
            "stock.picking": "picking",
            "account.move.line": "aml",
            "product.product": "product",
        }
        context = {recordtype.get(record._name): record}
        for rec in record.company_id.l10n_uy_edi_addenda_ids.filtered(
            lambda x: x.type == tipo_leyenda and x.apply_on in ["all", self._name]
        ):
            if bool(safe_eval.safe_eval(rec.condition, context)):
                res |= rec
        return res

    @api.constrains("move_type", "journal_id", "state")
    def _uy_ux_check_moves_use_documents(self):
        """Do not let to create not invoices entries in journals that use documents"""
        # TODO simil to _check_moves_use_documents. integrate somehow
        not_invoices = self.filtered(
            lambda x: (
                x.company_id.country_id.code == "UY"
                and x.journal_id.type in ["sale", "purchase"]
                and x.l10n_latam_use_documents
                and not x.is_invoice()
                and x.state == "posted"
            )
        )
        if not_invoices:
            raise ValidationError(
                self.env._(
                    "The selected Journal can't be used in this transaction, please select one that doesn't use documents"
                    " as these are just for Invoices."
                )
            )

    # TODO KZ esto lo usabamos para el tema de calcular autoamticamente las addendas, pero
    # no parece estar siendo usando, revisar si podemos borrar
    @api.model
    def is_zona_franca(self):
        """NOTE: Need to improve the way to identify the fiscal position"""
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

    def _is_manual_document_number(self):
        # EXTEND l10n_uy_edi
        """If we want to Get Uruware Invoice from manual journal then the document number
        should not be manual, will be added when syncronizing the data"""
        if (
            self.country_code == "UY"
            and self.journal_id.type == "sale"
            and self.journal_id.l10n_uy_edi_type == "manual"
            and self.manual_uruware_invoice
        ):
            return False
        return super()._is_manual_document_number()

    def action_l10n_uy_update_fields(self):
        """Sync with Uruware and complete vendor bill information."""
        self.ensure_one()
        if self.l10n_uy_edi_xml_attachment_id:
            self.clear_l10n_uy_invoice_fields()
        else:
            raise UserError(_("It is not possible to update the move because there is no xml file."))
        xml = base64.b64decode(self.l10n_uy_edi_xml_attachment_id.datas)
        self._l10n_uy_edi_complete_cfe_from_xml(etree.fromstring(xml))

    def clear_l10n_uy_invoice_fields(self):
        """When click the button "Update fields" in the vendor bill form view, firstly is neccessary to clean the
        invoices lines, the partner, the invoices date due and the payment type and if there is an error then is posted
        the message of the error in the invoice chatter."""
        error = False
        try:
            self = self.filtered(lambda x: x.invoice_filter_type_domain == "purchase").with_context(dynamic_unlink=True)
            self.line_ids.unlink()
            self.partner_id = False
            self.invoice_date_due = False
        except Exception as exp:
            error = exp
            self.env.cr.rollback()
        if error:
            msg = self.env._("We found an error when cleaning the information from the invoice: %s") % str(error)
            _logger.warning(msg)
            self.message_post(body=msg)

    def _l10n_uy_edi_update_xml_and_pdf_file(self, response):
        # TODO improve. Not sure why but this needed. if not then the compute not stored fields are not set
        self.l10n_uy_edi_document_id._compute_from_origin()
        return super()._l10n_uy_edi_update_xml_and_pdf_file(response)

    def _l10n_uy_edi_cfe_A_receptor(self):
        # EXTENDS: l10n_uy_edi
        """If sale_require_purchase_order_number OCA module is installed we change the value of the CompraID tag.
        The purchase order number to send to DGI will be extract from purchase_order_number field instead of ref field
        defined in odoo core"""
        res = super()._l10n_uy_edi_cfe_A_receptor()
        oca_module_installed = (
            self.env["ir.module.module"]
            .sudo()
            .search(
                [
                    ("name", "=", "sale_require_purchase_order_number"),
                    ("state", "in", ["installed", "to upgrade"]),
                ]
            )
        )
        if oca_module_installed and self.company_id.l10n_uy_edi_ucfe_env != "demo" and res:
            res["CompraID"] = self.purchase_order_number and self.purchase_order_number[:50] or None
        return res
