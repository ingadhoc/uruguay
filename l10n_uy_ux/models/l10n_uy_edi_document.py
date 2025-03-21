import logging

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)


class L10nUyEdiDocument(models.Model):
    _inherit = "l10n_uy_edi.document"

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
        ).mapped("code")
        if user_report_params:
            if "Parametros" not in endpoint:
                endpoint += "ConParametros"
                params = {
                    "nombreParametros": {"string": []},
                    "valoresParametros": {"string": []},
                }
            # Si el usuario definió separar la adenda, lo agregamos a los parámetros
            if "adenda" in user_report_params[0]:
                params["nombreParametros"]["string"].append("adenda")
                params["valoresParametros"]["string"].append("true")
            # Si el usuario definió un idioma, lo agregamos a los parámetros
            if "ingles" in user_report_params[1] and self.l10n_latam_document_type_id.code in available_doc_codes:
                params["nombreParametros"]["string"].append("reporte")
                params["valoresParametros"]["string"].append("ingles")
            if "secundario" in user_report_params[1]:
                params["nombreParametros"]["string"].append("reporte")
                params["valoresParametros"]["string"].append("secundario")

        return endpoint, params

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
