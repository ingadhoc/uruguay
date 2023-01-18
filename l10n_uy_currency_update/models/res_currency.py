from odoo import _, fields, models
from odoo.exceptions import UserError


class ResCurrency(models.Model):

    _inherit = "res.currency"

    l10n_uy_bcu_code = fields.Integer('Código BCU', help='Este codigo idenfica cada moneda y permite extraer el valor de la tasa del Banco Central Uruguayo')

    def action_l10n_uy_get_bcu_rate(self):
        """ Boton disponible en la vista formulario de moneda que permite consultar cual es la ultima fecha y cotizacion
        del ultimo cierre del bcu """
        self.ensure_one()
        if not self.l10n_uy_bcu_code:
            raise UserError(_('No BCU code for currency %s. Please configure the BCU code consulting information in BCU page https://www.bcu.gub.uy/Estadisticas-e-Indicadores/Paginas/Cotizaciones.aspx') % self.name)
        if self.name == 'UYU':
            raise UserError(_('No rate for UYU (is the base currency in Uruguay)'))

        last_date = self.env.company.get_bcu_last_date()
        rate_data = self.env.company._get_uy_bcu_rate(last_date, self)[0]
        if rate_data:
            rate = rate_data.TCV            # TCV : Tasa cambio Venta / TCV Tasa de cambio Compras
            raise UserError(_('Fecha Ultimo Cierre') + ': %s' % last_date + '\n' + _('Rate:') + ' %s' % rate)

        raise UserError(_('No pudimos obtener la información solicitada'))

    def action_get_available_currencies(self):
        """ Get the currency codes available in BCU
        View specification in https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcumonedas/service.asmx?WSDL """
        self.ensure_one()

        client = self.env.company._get_bcu_client('awsbcumonedas')
        factory = client.type_factory('ns0')
        Entrada = factory.wsmonedasin(Grupo=0)
        response = client.service.Execute(Entrada)

        currencies = self.env['res.currency'].search([('l10n_uy_bcu_code', '!=', False)])
        configured = {}
        not_configured = {}

        for item in response:
            if item.Codigo in currencies.mapped('l10n_uy_bcu_code'):
                odoo_currency = currencies.filtered(lambda x: x.l10n_uy_bcu_code == item.Codigo)
                configured.update({item.Codigo: item.Nombre + "  (%s - ID %s)" % (odoo_currency.name, odoo_currency.id)})
            else:
                not_configured.update({item.Codigo: item.Nombre})

        message = "\n".join(["Código/ Moneda\n\n(Configuradas):"] + ["* %s - %s" % (key, value) for key, value in configured.items()])
        message += "\n\n" + "\n".join(["(No configuradas)"] + ["* %s - %s" % (key, value) for key, value in not_configured.items()])
        raise UserError(message)
