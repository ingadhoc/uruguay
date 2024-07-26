import re

from odoo import _, api, models


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
        return res"
