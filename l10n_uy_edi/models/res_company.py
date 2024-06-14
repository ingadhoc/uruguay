# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.zeep import Client, Transport
from requests import Session
from zeep.wsse.username import UsernameToken
from odoo.tools.safe_eval import safe_eval
from lxml import etree
import logging
import base64
from OpenSSL import crypto
from datetime import datetime
import os


_logger = logging.getLogger(__name__)


class UYTransport(Transport):
    def post(self, address, message, headers):
        """ We overwrite this method only to be able to save the xml request and response.
        This will only affect to the connections that are made n this field and it do not extend the original
        Transport class of zeep package.

        NOTE: we try using the HistoryPlugin to save the xml request/response but seems this one could have problems
        when using with multi thread/workers"""
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

    l10n_uy_ucfe_env = fields.Selection([('production', 'Production'), ('testing', 'Testing')], string='Environment')
    l10n_uy_ucfe_prod_env = fields.Text('Uruware Production Data', groups="base.group_system", default="{}")
    l10n_uy_ucfe_test_env = fields.Text('Uruware Testing Data', groups="base.group_system", default="{}")

    l10n_uy_report_params = fields.Char()
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
        " connect to DGI to validate electronic invoice. Please upload here the DGI certificate in PEM format.")
    l10n_uy_dgi_crt_fname = fields.Char('DGI Certificate name')
    l10n_uy_ucfe_get_vendor_bills = fields.Boolean('Create vendor bills from Uruware', groups="base.group_system")

    # @api.depends('l10n_uy_dgi_crt')
    # def _compute_l10n_uy_dgi_crt_fname(self):
    #     """ Set the certificate name in the company. Needed in unit tests, solved by a similar onchange method in
    #     res.config.settings while setting the certificate via web interface """
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
        if not all([self.l10n_uy_ucfe_env, self.l10n_uy_ucfe_user, self.l10n_uy_ucfe_password, self.l10n_uy_ucfe_commerce_code,
                   self.l10n_uy_ucfe_terminal_code, self.l10n_uy_ucfe_inbox_url, self.l10n_uy_ucfe_query_url]):
            if raise_exception:
                raise UserError(_('Please complete the ucfe data to test the connection on company %s' % (self.name)))
            return False

        # Por si por error colocan los datos de inicio de sesion de prod en testing
        if self.l10n_uy_ucfe_env == 'testing' and ('prod' in self.l10n_uy_ucfe_inbox_url or 'prod' in self.l10n_uy_ucfe_query_url):
            raise UserError(_('Ambiente de Testing pero con datos de producción, por favor revisa/ajusta la configuración'))
        return True

    def _uy_get_client(self, url, return_transport=False):
        """ Get zeep client to connect to the webservice """
        self.ensure_one()
        self._is_connection_info_complete()
        wsdl = url
        if not wsdl.endswith('?wsdl'):
            wsdl += '?wsdl'

        try:
            session = Session()
            session.verify = os.path.join(os.path.dirname(__file__), '../static/ssl/uy.crt')
            transport = UYTransport(session=session, operation_timeout=60, timeout=60)
            user_name_token = UsernameToken(self.l10n_uy_ucfe_user, self.l10n_uy_ucfe_password)
            client = Client(wsdl, transport=transport, wsse=user_name_token)
        except Exception as error:
            raise UserError(_('Connection is not working. This is what we get %s' % repr(error)))

        if return_transport:
            return client, transport
        return client

    def _l10n_uy_ucfe_inbox_operation(self, msg_type, extra_req={}, return_transport=False):
        """ Call Operation get in msg_type for UCFE inbox webservice """
        self.ensure_one()
        # TODO consumir secuencia creada en Odoo
        id_req = extra_req.get('IdReq', 1)
        now = datetime.utcnow()
        company = self.sudo()
        data = {'Req': {'TipoMensaje': msg_type, 'CodComercio': company.l10n_uy_ucfe_commerce_code,
                        'CodTerminal': company.l10n_uy_ucfe_terminal_code, 'IdReq': id_req},
                'CodComercio': company.l10n_uy_ucfe_commerce_code,
                'CodTerminal': company.l10n_uy_ucfe_terminal_code,
                'RequestDate': now.replace(microsecond=0).isoformat(),
                'Tout': '30000'}
        if extra_req:
            data.get('Req').update(extra_req)

        res = company._uy_get_client(company.l10n_uy_ucfe_inbox_url, return_transport=return_transport)
        client = res[0] if isinstance(res, tuple) else res
        transport = res[1] if isinstance(res, tuple) else False
        error_msg = False
        try:
            response = client.service.Invoke(data)
        except Exception as exp:
            error_msg = repr(exp)

        if error_msg:
            raise UserError(_('There was a problem with the connection, this is what we get: ') + error_msg)
        # Capture any other errors in the connection
        if response.ErrorCode:
            error_msg = 'Codigo: ' + str(response.ErrorCode)
            if response.ErrorMessage:
                error_msg += ' - ' + response.ErrorMessage

        return (response, transport) if return_transport else response

    def _l10n_uy_ucfe_query(self, method, req_data={}, return_transport=False):
        """ Call UCFE query webservices """
        company = self.sudo()
        res = company._uy_get_client(company.l10n_uy_ucfe_query_url, return_transport=return_transport)
        client = res[0] if isinstance(res, tuple) else res
        transport = res[1] if isinstance(res, tuple) else False
        response = client.service[method](**req_data)
        return (response, transport) if return_transport else response

    def _uy_get_environment_type(self):
        """ This method is used to return the environment type of the company (testing or production) and will raise an
        exception when it has not been defined yet """
        self.ensure_one()
        if not self.l10n_uy_ucfe_env:
            raise UserError(_('Uruware/DGI environment not configured for company "%s", please check accounting settings') % (self.name))
        return self.l10n_uy_ucfe_env

    def action_update_from_config(self):
        self.ensure_one()
        config = False
        if self.l10n_uy_ucfe_env == 'production':
            config = self.l10n_uy_ucfe_prod_env
        elif self.l10n_uy_ucfe_env == 'testing':
            config = self.l10n_uy_ucfe_test_env

        config = safe_eval(config or "{}")
        self.write(config)

    # TODO
    # Servicio para listados con autenticación en los cabezales SOAP
    # Url de publicación del servicio/ WebServicesListadosFE.svc

    # Servicio para obtener el Informe de cierre parcial de operaciones con autenticación en los cabezales SOAP:
    # Url de publicación del servicio/ WebServicesReportesFE.svc

    # 7.1.1 Consulta de CFE rechazados por DGI
    # Esta operación permitirá consultar los CFE rechazados de una empresa en determinada fecha.
    # Operación a invocar: ComprobantesPorEmpresaDenegadosPorDgi
    # Parámetros:
    # • rut, indicando el RUT de la empresa que emitió los CFE.
    # • fechaComprobante, indicando la fecha en la que se rechazaron los comprobantes.
    # Respuesta:
    # Arreglo de Comprobantes, conteniendo todos los comprobantes rechazados para la empresa indicada en la fch inform.
    # La entidad Comprobante contiene los siguientes campos:
    # ▪ CodigoComercio, conteniendo el código de la sucursal que emitió el comprobante.
    # ▪ CodigoTerminal, conteniendo el código del punto de emisión que emitió el comprobante.
    # ▪ Numero, conteniendo el número del comprobante.
    # ▪ Serie, conteniendo la serie del comprobante.
    # ▪ TipoCfe, conteniendo el tipo del CFE según su número indicado en DGI
    # ▪ Uuid, conteniendo el identificador externo asignado al CFE
