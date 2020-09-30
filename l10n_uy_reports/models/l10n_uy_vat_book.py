# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.tools.misc import format_date


class L10nARVatBook(models.AbstractModel):

    _name = "l10n_uy.vat.book"
    _inherit = "account.report"
    _description = "Uruguayan VAT Book"

    filter_date = {'date_from': '', 'date_to': '', 'filter': 'this_month'}
    filter_all_entries = False

    def _get_columns_name(self, options):
        return [
            {'name': _("Date"), 'class': 'date'},
            {'name': _("Type")},
            {'name': _("Document")},
            {'name': _("Name")},
            {'name': _("RUT")},
            {'name': _('Taxed'), 'class': 'number'},
            {'name': _('Not Taxed'), 'class': 'number'},
            {'name': _('VAT 10%'), 'class': 'number'},
            {'name': _('VAT 22%'), 'class': 'number'},
            {'name': _('Other Taxes'), 'class': 'number'},
            {'name': _('Total'), 'class': 'number'},
        ]

    def print_pdf(self, options):
        options.update({
            'journal_type': self.env.context.get('journal_type')
        })
        return super(L10nARVatBook, self).print_pdf(options)

    def print_xlsx(self, options):
        options.update({
            'journal_type': self.env.context.get('journal_type')
        })
        return super(L10nARVatBook, self).print_xlsx(options)

    @api.model
    def _get_report_name(self):
        journal_type = self.env.context.get('journal_type')
        # when printing report there is no key on context
        return {'sale': _('Sales VAT book'), 'purchase': _('Purchases VAT book')}.get(journal_type, _('VAT book'))

    @api.model
    def _get_lines(self, options, line_id=None):
        context = self.env.context
        journal_type = context.get('journal_type') or options.get('journal_type', 'sale')
        company_ids = context.get('company_ids')

        lines = []
        line_id = 0

        if journal_type == 'purchase':
            sign = 1.0
        else:
            sign = -1.0

        totals = {}.fromkeys(['taxed', 'not_taxed', 'vat_10', 'vat_22', 'other_taxes', 'total'], 0)
        domain = [('journal_id.type', '=', journal_type), ('journal_id.l10n_latam_use_documents', '=', True),
                  ('company_id', 'in', company_ids)]
        state = context.get('state')
        if state and state.lower() != 'all':
            domain += [('state', '=', state)]
        if context.get('date_to'):
            domain += [('date', '<=', context['date_to'])]
        if context.get('date_from'):
            domain += [('date', '>=', context['date_from'])]
        for rec in self.env['account.uy.vat.line'].search_read(domain):
            taxed = rec['base_10'] + rec['base_22']
            other_taxes = rec['other_taxes']
            totals['taxed'] += taxed
            totals['not_taxed'] += rec['not_taxed']
            totals['vat_10'] += rec['vat_10']
            totals['vat_22'] += rec['vat_22']
            totals['other_taxes'] += other_taxes
            totals['total'] += rec['total']

            if rec['type'] in ['in_invoice', 'in_refund']:
                caret_type = 'account.invoice.in'
            elif rec['type'] in ['out_invoice', 'out_refund']:
                caret_type = 'account.invoice.out'
            else:
                caret_type = 'account.move'
            lines.append({
                'id': rec['id'],
                'name': format_date(self.env, rec['invoice_date']),
                'class': 'date',
                'level': 2,
                'model': 'account.uy.vat.line',
                'caret_options': caret_type,
                'columns': [
                    {'name': rec['document_type_id'][-1]},
                    {'name': rec['move_name']},
                    {'name': rec['partner_name']},
                    {'name': rec['rut']},
                    {'name': self.format_value(sign * taxed)},
                    {'name': self.format_value(sign * rec['not_taxed'])},
                    {'name': self.format_value(sign * rec['vat_10'])},
                    {'name': self.format_value(sign * rec['vat_22'])},
                    {'name': self.format_value(sign * other_taxes)},
                    {'name': self.format_value(sign * rec['total'])},
                ],
            })
            line_id += 1

        lines.append({
            'id': 'total',
            'name': _('Total'),
            'class': 'o_account_reports_domain_total',
            'level': 0,
            'columns': [
                {'name': ''},
                {'name': ''},
                {'name': ''},
                {'name': ''},
                {'name': self.format_value(sign * totals['taxed'])},
                {'name': self.format_value(sign * totals['not_taxed'])},
                {'name': self.format_value(sign * totals['vat_10'])},
                {'name': self.format_value(sign * totals['vat_22'])},
                {'name': self.format_value(sign * totals['other_taxes'])},
                {'name': self.format_value(sign * totals['total'])},
            ],
        })
        return lines
