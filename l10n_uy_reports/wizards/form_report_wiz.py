from odoo import models, api, fields, _
from ast import literal_eval
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


# TODO this code used also for 13.0 new generic module
class FormReportWiz(models.TransientModel):

    _name = 'form.report.wiz'
    _description = 'Generate files for Uruguayan Declaration'

    company_id = fields.Many2one('res.company')
    date_from = fields.Date()
    date_to = fields.Date()
    date_period = fields.Char(compute="_compute_date_period")
    uy_form_id = fields.Selection([('2181', 'Form 2181')], 'Form', default="2181")
    state = fields.Selection([
        ('query', 'Query'),
        ('finished', 'Finished')],
        default='query',
    )

    @api.model
    def default_get(self, list_fields):
        res = super().default_get(list_fields)
        if not res.get('company_id'):
            last_month = fields.Date.subtract(fields.Date.today(), months=1)
            res['company_id'] = self.env.company.id
            res['date_from'] = fields.Date.start_of(last_month, 'month')
            res['date_to'] = fields.Date.end_of(last_month, 'month'),

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
        return self.env['account.move'].search(domain, order='invoice_date asc, name asc, id asc')

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
        data = {}

        # TODO KZ Importante. por lo que vimos en el archivo generado esta mezclando iva compras e iva ventas.
        line_code = {
            self._search_tax('vat_22', 'sale'): '502',  # 502 IVA Ventas Tasa Básica a Contribuyentes
            self._search_tax('vat_10', 'sale'): '503',  # 503 IVA Ventas Tasa Mínima a Contribuyentes
            self._search_tax('vat_22', 'purchase'): '505',  # 505 IVA Compras Plaza Tasa Básica
            self._search_tax('vat_10', 'purchase'): '506',  # 506 IVA Compras Plaza Tasa Mínima
        }

        invoices = self._get_invoices()
        grouped_inv = self.env['account.move'].read_group(
            [('id', 'in', invoices.ids)],
            fields=['id', 'partner_id', 'date'],
            groupby=['partner_id', 'date:month'],
            # orderby='invoice_date asc, name asc, id asc'
            lazy=False)

        import pdb
        pdb.set_trace()
        invoice_lines = invoices.mapped('line_ids').filtered(lambda x: x.tax_ids in list(line_code.keys()))
        # if not vat_taxes and any(
        #         t.tax_group_id.l10n_ar_vat_afip_code and t.tax_group_id.l10n_ar_vat_afip_code != '0'
        #         for t in inv.invoice_line_ids.mapped('tax_ids')):

        for inv in invoices:
            if inv.partner_id not in data:
                data[inv.partner_id.id] = {
                    'partner': inv.partner_id,
                    'invoices': invoices.filtered(lambda x: x.partner_id == partner),
                }
            else:
                lines = inv.filtered(lambda x: x.line_ids in list(line_code.keys()))
                for line in lines:
                    data[inv.partner_id.id][line_code.get(line.tax_id)] = line.amount
        for partner, invoices in data.items():
            taxes = [0 , 1]
            invoice_lines = invoices.mapped('line_ids').filtered(lambda x: x.tax_ids in taxes)
            for item in invoice_lines:

                # Campo 1 - RUT Informante. Num 12 (Si <12 dígitos completa con 0 a la izq)
                content_data = "{:012d};".format(self.company_id.vat)

                # Campo 2 - Formulario. Num 5
                content_data += "{:05d};".format(self.uy_form_id)

                # Campo 3 - Período (AAAAMM) Num 6. Ejemplo: 200306
                content_data += "{};".format(self.date_period)

                # Campo 4 - RUT Informado. Num 12
                content_data = "{:012d};".format(item.invoce_id.partner_id.vat)

                # Campo 5 - Factura AAAAMM Num 6. Ejemplo: 200305
                content_data = "{};".format(item.invoce_id.date.strftime("%Y%m"))

                # Campo 6 - Línea del Rubro 5 del Formulario
                content_data += "{};".format(item.line_code.get(tax_ids))

                # Campo 7 - Importe. Num 12. Ejemplo: 2750 ó -2750
                content_data += "{};".format(item.amount)

                lines.append(content_data)

        res = '\n'.join(lines)
        return res

    def action_get_files(self):
        """ Button that will generate the files for the selected options given"""
        self.ensure_one()
        getattr(self, '_get_form_%s_data' % self.uy_form_id)()

        if not self.field_ids:
            self.write({'state': 'finished'})
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        self._update()
        return self.next_cb()

    def next_cb(self):
        self.ensure_one()
        if self.partner_id:
            self.write({'partner_ids': [(3, self.partner_id.id, False)]})
        return self._next_screen()

    def _next_screen(self):
        self.ensure_one()
        self.refresh()
        values = {}
        values.update({'state': 'finished'})
        self.write(values)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
