from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import safe_eval


class L10nUyEdiDocument(models.Model):
    _inherit = "l10n_uy_edi.document"

    l10n_latam_document_type_id = fields.Many2one(
        "l10n_latam.document.type", "Document Type", related=False, compute="_compute_from_origin"
    )
    l10n_latam_document_number = fields.Char(related=False, compute="_compute_from_origin")
    company_id = fields.Many2one("res.company", related=False, compute="_compute_from_origin")
    partner_id = fields.Many2one("res.partner", related=False, compute="_compute_from_origin")

    def _get_origin_record(self):
        self.ensure_one()
        if self.move_id:
            return self.move_id
        if hasattr(self, "picking_id") and self.picking_id:
            return self.picking_id
        return False

    def _compute_from_origin(self):
        for res in self:
            origin = res._get_origin_record()
            res.l10n_latam_document_number = origin.l10n_latam_document_number
            res.l10n_latam_document_type_id = origin.l10n_latam_document_type_id
            res.company_id = origin.company_id
            res.partner_id = origin.partner_id

    @api.depends("l10n_latam_document_type_id", "l10n_latam_document_number")
    def _compute_display_name(self):
        """Before the edi documents where only moves, now we can have pickings and make relation between them, so
        better to show the doc type to easily identify the document

        Display nam: DocumentType prefix + CFE Number (Serie + Number)"""
        super()._compute_display_name()
        for cfe in self.filtered(lambda x: x.l10n_latam_document_number and x.l10n_latam_document_type_id):
            cfe.display_name = "%s %s" % (
                cfe.l10n_latam_document_type_id.doc_code_prefix,
                cfe.l10n_latam_document_number,
            )

    # Methods extend for l10n_uy_edi

    def action_update_dgi_state(self):
        # EXTEND l10n_uy_edi
        """Permitimos actualizar estado solo si tenemos UUID y solo si esta en esperando respuesta.
        Si hay error no hay nada que consultar, y si fue aceptado rechazado ya no necesita ser actualizado"""
        for doc in self.filtered(lambda x: x.move_id.move_type not in ["in_invoice", "in_refund"]):
            if not doc.uuid:
                raise UserError(self.env._("Please return a 'UUID CFE Key' in order to continue"))
            if doc.state == "error":
                raise UserError(self.env._("You can not obtain the invoice with errors"))
            if doc.state != "received":
                raise UserError(self.env._("You can not update the state of a accepted/rejected invoice"))

        super().action_update_dgi_state()

    @api.model
    def _is_connection_info_incomplete(self, company):
        # EXTEND l10n_uy_edi
        """Intenta mandar mensaje de error de alerta si estas en ambiente de testing con datos
        de producción

        Return:
            False if everything is ok,
            Message if there is a problem or something missing"""
        res = super()._is_connection_info_incomplete(company)
        inbox_url = self._get_ws_url("inbox", company)
        query_url = self._get_ws_url("query", company)

        # Just in case they put production info in a testing environment by mistake
        if company.l10n_uy_edi_ucfe_env == "testing" and ("prod" in inbox_url or "prod" in query_url):
            res = (res or "") + self.env._(
                "Testing environment with production data. Please check/adjust the configuration"
            )
        return res

    def _get_report_params(self):
        # EXTEND l10n_uy_edi
        """
        En Odoo oficial se imprime el reporte PDF en inglés sólo cuando el partner no es uruguayo,
        y la adenda en hoja separada siempre que supere las 6 líneas, teniendo un máximo de 140
        caracteres por línea.
        Extendemos para que los usuarios puedan definir el formato de reporte a utilizar, en casos
        diferentes a los que contempla Odoo oficial.
        Parámetros personalizados:
        - nombreParametros: puede contener "reporte", "formato" y/o "adenda"
        - valoresParametros: valores correspondientes respetando el orden
        - "reporte": nombre del reporte alternativo, "codigo" para códigos de ítems, o "ingles"
        - "formato": valor "rollo"
        - "adenda": valor "true" para adenda en página separada

        IMPORTANTE: Los valores personalizados de "reporte" (distintos de "ingles") deben ser únicos.
        No pueden coexistir múltiples valores para el parámetro "reporte".

        Ejemplos válidos:
        - [["adenda"], ["true"]]
        - [["reporte"], ["ingles"]]
        - [["reporte"], ["secundario"]]
        - [["adenda", "reporte"], ["true", "ingles"]]

        Ejemplos NO válidos:
        - [["reporte", "reporte"], ["secundario", "ingles"]]
        """
        endpoint, params = super()._get_report_params()
        user_report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or "[]")

        available_doc_codes = (
            self.env.ref("l10n_uy.dc_e_ticket")
            | self.env.ref("l10n_uy.dc_cn_e_ticket")
            | self.env.ref("l10n_uy.dc_dn_e_ticket")
            | self.env.ref("l10n_uy.dc_e_inv_exp")
            | self.env.ref("l10n_uy.dc_cn_e_inv_exp")
            | self.env.ref("l10n_uy.dc_dn_e_inv_exp")
            | self.env.ref("l10n_uy.dc_e_remito")
        ).mapped("code")

        user_params = {}
        if user_report_params:
            if "Parametros" not in endpoint:
                endpoint += "ConParametros"

            user_params["nombreParametros"] = {"string": []}
            user_params["valoresParametros"] = {"string": []}

            for param_name, param_value in zip(user_report_params[0], user_report_params[1]):
                if param_name in ["adenda", "formato", "reporte"]:
                    if (
                        param_name == "reporte"
                        and param_value == "ingles"
                        and self.l10n_latam_document_type_id.code not in available_doc_codes
                    ):
                        continue
                    user_params["nombreParametros"]["string"].append(param_name)
                    user_params["valoresParametros"]["string"].append(param_value)

        return endpoint, user_params or params

    def unlink(self):
        """Extendemos unlink para prevenir la eliminación de documentos EDI que tienen errores.

        El módulo oficial l10n_uy_edi elimina documentos EDI con errores después del action_post,
        pero nosotros queremos preservar esos errores para que sean visibles en la factura posteada.
        """
        # Prevenir eliminación de documentos que tienen errores (mensajes)
        # Solo permitir eliminación si NO hay mensaje de error O si es eliminación manual
        docs_with_errors = self.filtered(lambda doc: doc.message and doc.move_id.l10n_uy_edi_error)
        docs_to_delete = self - docs_with_errors

        # Solo eliminar documentos que NO tienen errores
        if docs_to_delete:
            return super(L10nUyEdiDocument, docs_to_delete).unlink()

        return True

    # Metodos nuevos

    def ux_uy_get_last_invoice_number(self, document_type):
        """Cuando la persona no tiene configurado para emitir el docuemnto en uruware deberia de saltarle
        este error. Necesitamos ver si lo agregamos a los check_moves

        El dia de mañana si quieremos un Consultar Comprobante de DGI podemos usar esto
        660 - Query to get next CFE number

        NOTE: This method take into account regular CFE documents (code < 200),
        does not take into account contingency documents

        With the document_type return the next number to be use for that document type.
        """
        # TODO este metodo esta implementado y funciona pero no lo estamos usando. tenemos dos opciones
        # 1. lo agregamos como un wizard similar a consultar ultimo DGI
        # 2. lo agregamos como parte de los checks, pero para ello necesitamos adaptarlo ya que no
        #    existe aun el edi_doc.
        self.ensure_one()
        res = False
        if int(document_type.code) != 0 and int(document_type.code) < 200:
            result = self._ucfe_inbox("660", {"TipoCfe": document_type.code})
            if errors := result.get("errors"):
                raise UserError(
                    self.env._("We were not able to get the info of the next invoice number: %(error)s", error=errors)
                )

            response = result.get("response")
            if response is not None:
                next_number = response.findtext(".//{*}NumeroCfe", "")
                if not next_number:
                    raise UserError(
                        self.env._(
                            "You are not enabled to issue this document %(document)s, Please check your configuration settings",
                            document=document_type.display_name,
                        )
                    )
                res = int(next_number)
        return res
