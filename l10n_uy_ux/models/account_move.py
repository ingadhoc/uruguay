import logging

from odoo import api, models, fields, _

from odoo.exceptions import UserError, ValidationError
from odoo.tools import safe_eval


_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = "account.move"

    l10n_latam_document_type_id = fields.Many2one(change_default=True)
    # This is needed to be able to save default values
    # TODO KZ hacer pr a 17 o master pidiendo que hagan este fix directamtne en el modulo de l10n_latam_base

    # EXTENDS

    def _l10n_uy_edi_get_addenda(self):
        # EXTEND l10n_uy_edi
        """ Agrega el campo referencia como parte de la adenda """
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
