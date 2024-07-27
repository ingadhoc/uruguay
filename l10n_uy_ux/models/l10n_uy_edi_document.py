import re

from odoo import _, api, models
from odoo.exceptions import UserError

class L10nUyEdiDocument(models.Model):
    _inherit = 'l10n_uy_edi.document'

    def _get_ws_url(self, ws_endpoint, company):
        """ Manage both testing and production url at once """
        if ws_endpoint == 'inbox':
            prod = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_uy_edi.l10n_uy_edi_ucfe_inbox_url_production', 'https://prod6109.ucfe.com.uy/inbox115/cfeservice.svc')
            test = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_uy_edi.l10n_uy_edi_ucfe_inbox_url_testing', 'https://odootest.ucfe.com.uy/inbox115/cfeservice.svc')
            url = prod if company.l10n_uy_edi_ucfe_env == 'production' else test
            pattern = 'https://.*.ucfe.com.uy/inbox.*/cfeservice.svc'
        elif ws_endpoint == 'query':
            prod = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_uy_edi.l10n_uy_edi_ucfe_query_url_production',
                'https://prod6109.ucfe.com.uy/query116/webservicesfe.svc')
            test = self.env['ir.config_parameter'].sudo().get_param(
                'l10n_uy_edi.l10n_uy_edi_ucfe_query_url_testing',
                'https://odootest.ucfe.com.uy/query116/webservicesfe.svc')
            url = prod if company.l10n_uy_edi_ucfe_env == 'production' else test
            pattern = 'https://.*.ucfe.com.uy/query.*/webservicesfe.svc'

        res = url if re.match(pattern, url, re.IGNORECASE) is not None else False
        print("---- _get_ws_url %s" % res)
        return res

    @api.model
    def _is_connection_info_incomplete(self, company):
        """ False if everything is ok, Message if there is a problem or something missing """
        res = super()._is_connection_info_incomplete(company)
        inbox_url = self._get_ws_url('inbox', company)
        query_url = self._get_ws_url('query', company)

        # Just in case they put production info in a testing environment by mistake
        if company.l10n_uy_edi_ucfe_env == 'testing' and ('prod' in inbox_url or 'prod' in query_url):
            return _('Testing environment with production data. Please check/adjust the configuration')
        return res

    def _get_dgi_last_invoice_number(self, document_type):
        """ En este momento no lo usamos, en la version anterior lo usabamos para calcular la secuencia del proximo numero a usar.
        Realmente no era necesario y ya no lo hacemos, sin embargo quedo aca implementado.

        El dia de mañana si quieremos un Consultar Comprobante de DGI podemos usar esto que ya esta implementado
        ENDPOINT: 660 - Query to get next CFE number

        NOTE: This method take into account regular CFE documents (code < 200),
        does not take into account contingency documents

        With the document_type return the next number to be use for that document type.

        TODO KZ IMPORTANTE: Cuando la persona no tiene configurado para emitir el docuemnto en uruware deberia de saltarle este error.
        Necesitamos ver si lo agregamos a los check_moves """
        self.ensure_one()
        res = False
        if self.l10n_uy_edi_type == "electronic" and int(document_type.code) != 0 and int(document_type.code) < 200:
            result = self._ucfe_inbox("660", {"TipoCfe": document_type.code})
            if errors := result.get('errors'):
                raise UserError(_(
                    "We were not able to get the info of the next invoice number: %(error)s", error=errors))

        response = result.get('response')
        if response is not None:
            next_number = response.findtext(".//{*}NumeroCfe", "")
            if not next_number:
                raise UserError(_(
                    "You are not enabled to issue this document %(document)s, Please check your configuration settings",
                    document=document_type.display_name))
            res = int(next_number)
        return res
