# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError
from zeep import Client, transports
from zeep.wsse.username import UsernameToken
from lxml import etree
import logging


_logger = logging.getLogger(__name__)


class UYTransport(transports.Transport):
    def post(self, address, message, headers):
        """ We overwrite this method only to be able to save the xml request and response.
        This will only affect to the connections that are made n this field and it do not extend the original
        Transport class of zeep package.

        NOTE: we try using the HistoryPlugin to save the xml request/response but seems this one could have problems when using with multi thread/workers"""
        response = super().post(address, message, headers)
        self.xml_request = etree.tostring(
            etree.fromstring(message), pretty_print=True).decode('utf-8')
        self.xml_response = etree.tostring(
            etree.fromstring(response.content), pretty_print=True).decode('utf-8')
        return response


class ResCompany(models.Model):

    _inherit = "res.company"

    l10n_uy_uruware_user = fields.Char('Uruware User', groups="base.group_system")
    l10n_uy_uruware_password = fields.Char('Uruware Password', groups="base.group_system")
    l10n_uy_uruware_commerce_code = fields.Char('Uruware Commerce code', groups="base.group_system")
    l10n_uy_uruware_terminal_code = fields.Char('Uruware Terminal code', groups="base.group_system")
    l10n_uy_uruware_inbox_url = fields.Char('Uruware Inbox URL', groups="base.group_system")
    l10n_uy_uruware_query_url = fields.Char('Uruware Query URL', groups="base.group_system")

    def _is_connection_info_complete(self, raise_exception=True):
        """ Raise exception if not all the connection info is available """
        if not all([self.l10n_uy_uruware_user, self.l10n_uy_uruware_password, self.l10n_uy_uruware_commerce_code,
                   self.l10n_uy_uruware_terminal_code, self.l10n_uy_uruware_inbox_url, self.l10n_uy_uruware_query_url]):
            if raise_exception:
                raise UserError(_('Please complete the uruware data to test the connection'))
            return False
        return True

    def _get_client(self, return_transport=False):
        """ Get zeep client to connect to the webservice """
        self.ensure_one()
        self._is_connection_info_complete()
        auth = {'Username': self.l10n_uy_uruware_user, 'Password': self.l10n_uy_uruware_password}

        wsdl = self.l10n_uy_uruware_inbox_url
        if not wsdl.endswith('?wsdl'):
            wsdl += '?wsdl'

        try:
            transport = UYTransport(operation_timeout=60, timeout=60)
            client = Client(wsdl, transport=transport, wsse=UsernameToken(self.l10n_uy_uruware_user, self.l10n_uy_uruware_password))
        except Exception as error:
            raise UserError(_('Connection is not working. This is what we get %s' % repr(error)))

        if return_transport:
            return client, auth, transport
        return client, auth
