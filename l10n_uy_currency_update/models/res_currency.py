from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools.zeep import Client

import logging
_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):

    _inherit = "res.currency"

    l10n_uy_have_bcu_code = fields.Boolean(store=False,compute='_compute_l10n_uy_bcu_have_code')

    def _compute_l10n_uy_bcu_have_code(self):
        """
        Compute if a currency has a BCU code (Central Bank of Uruguay) available.
        - The method uses the `res.currency` model to obtain the active currencies.
        - It uses the `_parse_bcu_data` method from the `res.company` model to retrieve exchange rate data.

        It does not return any value but updates the `l10n_uy_have_bcu_code` field in each record of the current model.
        This will help us hide the buttons in the view of l10n_uy_currency_update/views/res_currency_views.xml
        """
        available_currencies = self.env['res.currency'].search([])
        rate = self.env['res.company']._parse_bcu_data(available_currencies)
        for rec in self:
            if rec.name in rate.keys():
                rec.l10n_uy_have_bcu_code = True
                continue
            rec.l10n_uy_have_bcu_code = False

    def action_l10n_uy_get_bcu_rate(self):
        available_currencies = self.env['res.currency'].search([])
        rate = self.env['res.company']._parse_bcu_data(available_currencies)
        if self.name in rate:
            raise UserError(_('Fecha Ultimo Cierre: %s\nRate: %s' % (rate[self.name][1], rate[self.name][0])))
        else:
            raise UserError(_('No se encontro cotizacion para esta Moneda'))

    def action_get_available_currencies(self):
        """ Get the currency codes available in BCU
        View specification in https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcumonedas/service.asmx?WSDL """
        self.ensure_one()

        wsdl = "https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcumonedas/service.asmx?WSDL"
        try:
            available_currencies_client = Client(wsdl)
            factory = available_currencies_client.type_factory('ns0')
            Entrada = factory.wsmonedasin(Grupo=0)
            response = available_currencies_client.service.Execute(Entrada)
            currencies = self.env['res.company']._get_bcu_currencies_mapping()
        except ValueError as exp:
            msg = 'No se pudo conectar al webservice para extraer datos de moneda: ' + str(exp)
            _logger.warning(msg=msg)
            raise UserError(msg)

        configured = {}
        not_configured = {}
        currencie_list = currencies.values()
        invert_currencie_dict = {valor: clave for clave, valor in currencies.items()}
        for item in response:
            if item.Codigo in currencie_list:
                odoo_currency = self.search([('name', '=', invert_currencie_dict[item.Codigo])], limit=1)
                configured.update({item.Codigo: item.Nombre + " (%s - ID %s)" % (odoo_currency.name, odoo_currency.id)})
            else:
                not_configured.update({item.Codigo: item.Nombre})

        message = "\n".join(["Código/ Moneda\n\n(Configuradas):"] + ["* %s - %s" % (key, value) for key, value in configured.items()])
        message += "\n\n" + "\n".join(["(No configuradas)"] + ["* %s - %s" % (key, value) for key, value in not_configured.items()])
        raise UserError(message)
