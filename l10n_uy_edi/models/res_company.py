# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from zeep import Client, transports
from zeep.wsse.username import UsernameToken
from lxml import etree
import logging
import base64
from OpenSSL import crypto
from datetime import datetime


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

    # Uruware
    l10n_uy_ucfe_user = fields.Char('Uruware User', groups="base.group_system")
    l10n_uy_ucfe_password = fields.Char('Uruware Password', groups="base.group_system")
    l10n_uy_ucfe_commerce_code = fields.Char('Uruware Commerce code', groups="base.group_system")
    l10n_uy_ucfe_terminal_code = fields.Char('Uruware Terminal code', groups="base.group_system")
    l10n_uy_ucfe_inbox_url = fields.Char('Uruware Inbox URL', groups="base.group_system")
    l10n_uy_ucfe_query_url = fields.Char('Uruware Query URL', groups="base.group_system")

    # DGI
    l10n_uy_dgi_house_code = fields.Integer(
        "Código Casa Principal/Sucursal", default=1, help="Este valor es parte del XML cuando se envia el CFE."
        " Campo 47 (Emisor/CdgDGISucur)"
        "\nPara obtener ese datos podrias seguir los siguientes datos:"
        "\n1. Ingresar a la pagina de servicios en linea de DGI."
        "\n2. Seleccionar la opción Registro único tributario -> Consulta de datos (es un link del menú de la derecha)."
        "\n3. Seleccionar Consulta de Datos Registrales -> Consulta de Datos de Entidades."
        "\n4. Se abre un PDF. El dato aparece en Domicilio Fiscal -> Número de Local")
    l10n_uy_dgi_crt = fields.Binary(
        'DGI Certificate', groups="base.group_system", help="This certificate lets us"
        " connect to DGI to validate electronic invoice. Please upload here the AFIP certificate in PEM format.")
    l10n_uy_dgi_crt_fname = fields.Char('DGI Certificate name')

    # @api.depends('l10n_uy_dgi_crt')
    # def _compute_l10n_uy_dgi_crt_fname(self):
    #     """ Set the certificate name in the company. Needed in unit tests, solved by a similar onchange method in res.config.settings while setting the certificate via web interface """
    #     with_crt = self.filtered(lambda x: x.l10n_uy_dgi_crt)
    #     remaining = self - with_crt
    #     for rec in with_crt:
    #         # certificate = self._l10n_uy_get_certificate_object(rec.l10n_uy_dgi_crt)
    #         # rec.l10n_uy_dgi_crt_fname = certificate.get_subject().CN
    #         rec.l10n_uy_dgi_crt_fname = ''

    # def _l10n_uy_get_certificate_object(self, cert):
    #     crt_str = base64.decodestring(cert).decode('ascii')
    #     res = crypto.load_certificate(crypto.FILETYPE_PEM, crt_str)
    #     import pdb; pdb.set_trace()
    #     return res

    def _is_connection_info_complete(self, raise_exception=True):
        """ Raise exception if not all the connection info is available """
        if not all([self.l10n_uy_ucfe_user, self.l10n_uy_ucfe_password, self.l10n_uy_ucfe_commerce_code,
                   self.l10n_uy_ucfe_terminal_code, self.l10n_uy_ucfe_inbox_url, self.l10n_uy_ucfe_query_url]):
            if raise_exception:
                raise UserError(_('Please complete the ucfe data to test the connection'))
            return False
        return True

    def _get_client(self, return_transport=False):
        """ Get zeep client to connect to the webservice """
        self.ensure_one()
        self._is_connection_info_complete()
        auth = {'Username': self.l10n_uy_ucfe_user, 'Password': self.l10n_uy_ucfe_password}

        wsdl = self.l10n_uy_ucfe_inbox_url
        if not wsdl.endswith('?wsdl'):
            wsdl += '?wsdl'

        try:
            transport = UYTransport(operation_timeout=60, timeout=60)
            user_name_token = UsernameToken(self.l10n_uy_ucfe_user, self.l10n_uy_ucfe_password)
            client = Client(wsdl, transport=transport, wsse=user_name_token)

            # TESTING 1
            # from requests import Session
            # from odoo.modules.module import get_module_resource
            # session = Session()
            # session.verify = get_module_resource('l10n_uy_edi', 'demo', 'CorreoUruguayoCA.crt')
            # transport = UYTransport(session=session, operation_timeout=60, timeout=60)
            # client = Client(wsdl, transport=transport, wsse=UsernameToken(self.l10n_uy_ucfe_user, self.l10n_uy_ucfe_password))
            # # RESULT
            # # Connection is not working. This is what we get SSLError(MaxRetryError('HTTPSConnectionPool(host=\'test.ucfe.com.uy\', port=443): Max retries exceeded with url: /Inbox115/CfeService.svc?wsdl (Caused by SSLError(SSLError("bad handshake: Error([(\'SSL routines\', \'tls_process_server_certificate\', \'certificate verify failed\')],)",),))',),)

            # TESTING 2
            # from zeep.wsse.signature import Signature
            # signature = Signature(private_key_filename, public_key_filename, optional_password)
            # client = Client(wsdl, transport=transport, wsse=[user_name_token, signature])

        except Exception as error:
            raise UserError(_('Connection is not working. This is what we get %s' % repr(error)))

        if return_transport:
            return client, auth, transport
        return client, auth

    def _l10n_uy_get_data(self, msg_type, extra_req={}):
        self.ensure_one()
        # TODO I think this should be unique? see how we can generated it,  int, need to be assing using a
        # sequence in odoo? consumir secuencia creada en Odoo
        id_req = 1

        now = datetime.utcnow()
        data = {'Req': {'TipoMensaje': msg_type, 'CodComercio': self.l10n_uy_ucfe_commerce_code,
                        'CodTerminal': self.l10n_uy_ucfe_terminal_code, 'IdReq': id_req},
                'CodComercio': self.l10n_uy_ucfe_commerce_code,
                'CodTerminal': self.l10n_uy_ucfe_terminal_code,
                'RequestDate': now.replace(microsecond=0).isoformat(),
                'Tout': '30000'}
        if extra_req:
            data.get('Req').update(extra_req)
        return data
