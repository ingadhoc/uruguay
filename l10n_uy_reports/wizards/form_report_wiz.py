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

    def _get_invoices(self):
        """ Both customer and vendor bills """
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id), ('state', '=', 'posted'),
            ('date', '>=', self.date_from), ('date', '<', self.date_to),
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
        line_code = {
            self._search_tax('vat_22', 'sale'): '502',  # 502 IVA Ventas Tasa Básica a Contribuyentes
            self._search_tax('vat_10', 'sale'): '503',  # 503 IVA Ventas Tasa Mínima a Contribuyentes
            self._search_tax('vat_exempt', 'purchase'): '504',  # Compras Plaza Exentas de IVA
            self._search_tax('vat_22', 'purchase'): '505',  # 505 IVA Compras Plaza Tasa Básica
            self._search_tax('vat_10', 'purchase'): '506',  # 506 IVA Compras Plaza Tasa Mínima
        }
        # Estos dos parece que tambien van pero no tenemos un impuestos para colocarlo
        # ("507", "507	- IVA Ventas tasa 10% a Contribuyentes"),
        # ("508", "508	- IVA Compras Plaza Tasa 10%"),

        taxes_raw = list(line_code.keys())
        taxes = self.env['account.tax']
        for item in taxes_raw:
            taxes |= item

        tax_code = {}
        taxes_group_ids = taxes.mapped('tax_group_id').ids
        for tax in taxes:
            tax_code[tax.tax_group_id.id] = line_code.get(tax)

        invoices = self._get_invoices()
        UYU_currency = self.env.ref('base.UYU')

        # Revisando que todos los impuestos esten bien configurados
        error = ""
        for line in invoices.line_ids:
            if line.tax_ids and line.tax_ids not in taxes:
                error += "\n- %s %s" % (line.tax_ids.mapped("name"), line.move_id.display_name)
        if error:
            _logger.warning("No se puede genear declaracion de impuestos (config impuesto) para %s" % error)

        # Agrupamos por RUT
        data = {}
        for inv in invoices:
            if inv.partner_id.vat in data:
                data[inv.partner_id.vat] |= inv
            else:
                data[inv.partner_id.vat] = inv

        # Validaciones
        inv_wo_id_num = invoices.filtered(lambda x: not x.partner_id.vat)
        if inv_wo_id_num:
            raise UserError(
                _("No se puede generar archivo ya que no hay información del numero de RUT/RUC/DNI del receptor %s") %
                ''.join(["\n- %s %s" % (item.display_name, item.partner_id.display_name)
                         for item in inv_wo_id_num.mapped]))

        for rut_partner, invoices in data.items():
            temp = {}
            for inv in invoices:
                detail_amounts = json.loads(inv.tax_totals_json)
                for item in detail_amounts.get('groups_by_subtotal').get('Untaxed Amount'):
                    tax_group_id = item.get('tax_group_id')
                    if tax_group_id in taxes_group_ids:
                        amount = item.get('tax_group_amount')
                        # No estaba ene especifcacion pero vimos via un ejemplo que los montos reportados siempre son en
                        # pesos. aun qu el comprobamte sea de otra moneda, es por eso que hacemos esta conversion
                        if inv.currency_id != UYU_currency:
                            amount = amount * inv.l10n_uy_currency_rate
                        temp[tax_group_id] = (temp.get(tax_group_id, 0.0)) + amount
            for tax in temp:
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
                content_data += "{0:>015.2f};".format(temp.get(tax))

                lines.append(content_data)

        res = '\n'.join(lines)

        # TODO delete when we have resolve the pr
        import pprint
        pprint.pprint(res)
        return res

    def action_get_files(self):
        """ Button that will generate the files for the selected options given"""
        self.ensure_one()

        if self.company_id.country_id.code != 'UY':
            raise UserError(_("Solo puede generar este reporte para compañias Uruguayas"))

        data = getattr(self, '_get_form_%s_data' % self.uy_form_id)()
        self.res_filename = self.company_id.name[:4] + "Formulario2-181DGI_" + self.date_period[-2:] + self.date_period[:4] + ".txt"
        # TODO No sabemos realmente cual es el formato, solo tomamos de ejemplo el que genera uruware
        # Ejemplo SumiFormulario2-181DGI_10_2022.txt ver de mejorarlo del periodo

        self.res_file = base64.encodebytes(data.encode('ISO-8859-1'))
        if not self.res_file:
            raise UserError(_("Ningun archivo fue generado"))

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
