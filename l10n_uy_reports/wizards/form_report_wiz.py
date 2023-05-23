import base64
import json
import logging
from odoo import models, api, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class FormReportWiz(models.TransientModel):

    _name = 'form.report.wiz'
    _description = 'Generate files for Uruguayan Declaration'

    company_id = fields.Many2one('res.company')
    date_from = fields.Date()
    date_to = fields.Date()
    date_period = fields.Char(compute="_compute_date_period")
    uy_form_id = fields.Selection([('2181', 'Form 2181')], 'Form', default="2181")
    res_file = fields.Binary()
    res_filename = fields.Char()

    @api.model
    def default_get(self, list_fields):
        res = super().default_get(list_fields)
        if not res.get('company_id'):
            last_month = fields.Date.subtract(fields.Date.today(), months=1)
            res['company_id'] = self.env.company.id
            res['date_from'] = fields.Date.start_of(last_month, 'month')
            res['date_to'] = fields.Date.end_of(last_month, 'month')
        return res

    @api.depends('date_to', 'date_from')
    def _compute_date_period(self):
        for rec in self:
            rec.date_period = rec.date_to.strftime("%Y%m")

    @api.onchange('date_to', 'date_from')
    def _onchange_dates(self):
        """ Fix the date to and end to dates given by the user """
        init_of_month = fields.Date.start_of(self.date_from, "month")
        end_of_month = fields.Date.end_of(self.date_from, "month")
        self.date_from = init_of_month
        self.date_to = end_of_month

    def _get_invoices(self):
        """ Both customer and vendor bills

            * Solo debemos tomar en cuenta los cfe que tengan un partner con numero de identificacion, los que no no tenemos
              que tomarlos en cuenta ni enviar nada.
            * Solo tomar en cuenta los aceptados, el resto no
        """
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            '|', ('l10n_uy_cfe_state', 'in', ['accepted']), ('move_type', 'like', 'in_'),
            ('date', '>=', self.date_from), ('date', '<', self.date_to),
            ('partner_id.vat', '!=', False),
            ('l10n_latam_document_type_id.code', '!=', '0'),
            ('l10n_latam_document_type_id.code', '!=', False)
        ]
        res = self.env['account.move'].search(domain, order='invoice_date asc, name asc, id asc')
        return res

    def _search_tax(self, tax_name, tax_type):
        res = self.env['account.tax'].with_context(active_test=False).search([
            ('type_tax_use', '=', tax_type), ('company_id', '=', self.company_id.id),
            ('tax_group_id', '=', self.env.ref('l10n_uy_account.tax_group_' + tax_name).id)], limit=1)
        return res

    def _get_form_2181_data(self):
        """ Prepara the content of the file

        Este es un solo archivo TXT el cual contiene.
        En el Rubro 5 se ingresan agrupados por Identificación del contribuyente y número de línea
        correspondiente al concepto declarado e importe.

        Agrupado por partner, por periodo y fecha de factura la información de los impuestos generados

        return the string with the lines of the file to write """
        lines = []
        # TODO KZ Importante. por lo que vimos en el archivo generado esta mezclando iva compras e iva ventas.

        invoices = self._get_invoices()
        UYU_currency = self.env.ref('base.UYU')

        line_code = {}
        taxes = invoices.mapped('line_ids.tax_ids').filtered(lambda x: x.l10n_uy_dgi_code.form == "2181")
        for tax in taxes:
            line_code.update({tax: tax.l10n_uy_dgi_code.code})

        tax_code = {}
        taxes_group_ids = taxes.mapped('tax_group_id').ids
        for tax in taxes:
            tax_code[(tax.tax_group_id.id, tax.type_tax_use)] = line_code.get(tax)

        # Revisando que todos los impuestos esten bien configurados
        error = ""
        for line in invoices.line_ids:
            if line.tax_ids and line.tax_ids not in taxes:
                error += "\n- %s %s" % (line.tax_ids.mapped("name"), line.move_id.display_name)
        if error:
            _logger.warning("No se puede genear declaracion de impuestos (config impuesto) para %s" % error)

        # TODO KZ: Agrupamos por RUT pero sin tener en cuenta si no fue enviado el receptor entonces no se debe tomar en cuenta para el total)
        # Ejemplo un e-tTicket con monto pequeño de monto total. de lado de Odoo esta registrado para el Partner ABC.
        # Pero al final esa factura se envia sin datos del receptor a Uruware y DGI y no e reporta a DGI no se tiene que
        # informar. es por eso que debemos saltarlo aca. Intente consultado _l10n_uy_get_cfe_receptor
        # pero tenemos un problema. cuando se genera desde uruware no tenemos este dato. ver de mejorar
        data = {}
        for inv in invoices:
            # temp = inv._l10n_uy_get_cfe_receptor()
            # if not temp:
            #    continue
            if inv.partner_id.vat in data:
                data[inv.partner_id.vat] |= inv
            else:
                data[inv.partner_id.vat] = inv

        for rut_partner, invoices in data.items():
            amount_total = {}
            for inv in invoices:
                detail_amounts = json.loads(inv.tax_totals_json)
                for item in list(detail_amounts.get('groups_by_subtotal').values())[0]:
                    tax_group_id = item.get('tax_group_id')
                    if tax_group_id in taxes_group_ids:
                        inv_amount = item.get('tax_group_amount')
                        # No estaba ene especifcacion pero vimos via un ejemplo que los montos reportados siempre son en
                        # pesos. aun qu el comprobamte sea de otra moneda, es por eso que hacemos esta conversion
                        if inv.currency_id != UYU_currency:
                            inv_amount = inv_amount * inv.l10n_uy_currency_rate
                        key = (tax_group_id, 'sale' if 'out_' in inv.move_type else 'purchase')
                        amount_total[key] = amount_total.get(key, 0.0) + (amount_total.get(tax_group_id, 0.0)) + inv_amount
            for tax in amount_total:

                # Campo 1 - RUT Informante. Num 12 (Si <12 dígitos completa con 0 a la izq)
                content_data = self.company_id.vat.zfill(12) + ";"

                # Campo 2 - Formulario. Num 5
                content_data += "{: 5d};".format(int(self.uy_form_id))

                # Campo 3 - Período (AAAAMM) Num 6. Ejemplo: 200306
                content_data += "{};".format(self.date_period)

                # Campo 4 - RUT Informado. Num 12
                content_data += rut_partner.zfill(12) + ";"

                # Campo 5 - Factura AAAAMM Num 6. Ejemplo: 200305
                content_data += "{};".format(line.move_id.date.strftime("%Y%m"))

                # Campo 6 - Línea del Rubro 5 del Formulario
                content_data += "{};".format(tax_code.get(tax))

                # Campo 7 - Importe. Num 12. Ejemplo: 2750 ó -2750
                content_data += "{0:>015.2f};".format(amount_total.get(tax))

                lines.append(content_data)

        res = '\n'.join(lines)
        return res

    def action_get_files(self):
        """ Button that will generate the files for the selected options given"""
        self.ensure_one()

        if self.company_id.country_id.code != 'UY':
            raise UserError(_("Solo puede generar este reporte para compañias Uruguayas"))

        data = getattr(self, '_get_form_%s_data' % self.uy_form_id)()
        if data:
            self.res_filename = self.company_id.name[:4] + "Formulario2-181DGI_" + self.date_period[-2:] + self.date_period[:4] + ".txt"
            # TODO No sabemos realmente cual es el formato, solo tomamos de ejemplo el que genera uruware
            # Ejemplo SumiFormulario2-181DGI_10_2022.txt ver de mejorarlo del periodo
            self.res_file = base64.encodebytes(data.encode('ISO-8859-1'))
        else:
            self.res_filename = "Ningun archivo fue generado"
            self.res_file = False

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
