##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
from zeep import transports
import zeep
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):

    _inherit = 'res.company'

    currency_provider = fields.Selection(
        selection_add=[('bcu', 'Webservices BCU - Banco Central (Uruguay)')],
    )

    @api.model_create_multi
    def create(self, vals_list):
        """ Overwrite to include new currency provider """
        for vals in vals_list:
            if vals.get('country_id') and 'currency_provider' not in vals:
                country = self.env['res.country'].browse(vals['country_id'])
                if country.code.upper() == 'UY':
                    vals['currency_provider'] = 'bcu'
            return super().create(vals_list)

    @api.model
    def _compute_currency_provider(self):
        """ Overwrite to include new currency provider """
        super()._compute_currency_provider()
        uy_companies = self.search([]).filtered(lambda company: company.country_id.code == 'UY')
        if uy_companies:
            uy_companies.currency_provider = 'bcu'
            _logger.log(25, "Currency Provider configured as BCU for next companies: %s", ', '.join(
                uy_companies.mapped('name')))

    @api.model
    def _get_bcu_client(self, bcu_service, return_transport=False):
        """ Get zeep client to connect to the webservice """
        # consultar cotizaciones
        wsdl = "https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/" + bcu_service + "/service.asmx?WSDL"

        operation_timeout = timeout = 60
        try:
            transport = transports.Transport(operation_timeout=operation_timeout, timeout=timeout)
            client = zeep.Client(wsdl, transport=transport)
        except Exception as error:
            raise error

        if return_transport:
            return client, transport
        return client

    def _parse_bcu_data(self, available_currencies):
        """ This method is used to update the currency rates using BCU provider. Rates are given against UY
        return dictionary of form currency_iso_code: (rate, date_rate) """
        available_currencies = available_currencies or self.env['res.currency'].search([])
        currency_uy = self.env.ref('base.UYU')
        available_currencies = available_currencies.filtered('l10n_uy_bcu_code') - currency_uy

        if not available_currencies:
            _logger.log(25, "Not available currencies to update BCU UY")
            return False

        code_currencies = {'item': available_currencies.mapped('l10n_uy_bcu_code')}
        # code_currencies = [0]   # Todas las monedas
        # code_currencies = {'item': [2224, 500, 501]} # Argentino, y Argentino Billete

        today = fields.Date.context_today(self.with_context(tz='America/Montevideo'))
        last_date = self.env.company.get_bcu_last_date()
        yesterday = (today - relativedelta(days=1))

        # NOTA: Esto fue necesario agregarlo porque sino me saltaba este error al correr actualizar moneda con proveedor
        # BCU: ""Su moneda principal (UYU) no es soportada por este servicio de tasas de cambio. Favor de elegir otro.""
        # Si logramos un mejora manera de definir esto mejor, porque estamos creando la tasa de moneda UYU todos los
        # dias con tasa 1, y no tiene sentido :(
        res = {'UYU': (1.0, today)}

        if last_date != yesterday:
            return False

        response_data = []

        try:
            _logger.log(25, "Connecting to BCU to update the currency rates for %s", available_currencies.mapped('name'))
            client = self._get_bcu_client('awsbcucotizaciones')
            factory = client.type_factory('ns0')
            Entrada = factory.wsbcucotizacionesin(Moneda=code_currencies, FechaDesde=yesterday, FechaHasta=yesterday, Grupo=0)
            response = client.service.Execute(Entrada)
            response_data = response.datoscotizaciones['datoscotizaciones.dato']
            if response.respuestastatus.codigoerror:
                raise UserError(_('Error encontrado al conectar para a UY BCU para actualizar moneda') + ': %s' % response.respuestastatus.mensaje)

        except Exception as exp:
            _logger.log(25, "Could not get rate for currencies %s. This is what we get:\n%s", available_currencies.mapped('name'), exp)

        for rate_data in response_data:
            # bcu_date = rate_data.Fecha  # Fecha de la cotización
            rate = rate_data.TCV        # TCV : Tasa cambio Venta / TCV Tasa de cambio Compras

            # necesitamos hacer esto para las monedas qu eno cumplen codigo iso ejemplo Unidad Indexada Uruguaya. En odoo lo tenemos como UYI
            # y en el ws lo tenemos como U.I. (este ultimo no es un valor valido segun odoo paraname de moneda - codigo iso)
            odoo_currency = available_currencies.filtered(lambda x: x.l10n_uy_bcu_code == rate_data.Moneda)
            res.update({odoo_currency.name: (1.0 / rate, today)})
            _logger.log(25, "Currency %s %s %s", rate_data.CodigoISO, today, rate)
        return res or False

    def get_bcu_last_date(self):
        """ Get the currency codes available in BCU
        View specification in https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsultimocierre/service.asmx?WSDL """
        self.ensure_one()
        client = self._get_bcu_client('awsultimocierre')
        response = client.service.Execute()
        return response
