# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _


class UruguayanReportCustomHandler(models.AbstractModel):
    _name = 'l10n_uy.tax.report.handler'
    _inherit = 'account.generic.tax.report.handler'
    _description = 'Uruguayan Report Custom Handler'

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals):
        # dict of the form {move_id: {column_group_key: {expression_label: value}}}
        move_info_dict = {}

        # dict of the form {column_group_key: total_value}
        total_values_dict = {}

        # Every key/expression_label that is a number (and should be rendered like one)
        number_keys = ['taxed', 'not_taxed', 'vat_10', 'vat_22', 'other_taxes', 'total']

        # Build full query
        query_list = []
        full_query_params = []
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            query, params = self._build_query(report, column_group_options, column_group_key)
            query_list.append(f"({query})")
            full_query_params += params

            # Set defaults here since the results of the query for this column_group_key might be empty
            total_values_dict.setdefault(column_group_key, dict.fromkeys(number_keys, 0.0))

        full_query = " UNION ALL ".join(query_list)
        self._cr.execute(full_query, full_query_params)
        results = self._cr.dictfetchall()
        for result in results:
            # Iterate over these results in order to fill the move_info_dict dictionary
            move_id = result['id']
            column_group_key = result['column_group_key']

            # For number rendering, take the opposite for sales taxes
            sign = -1.0 if result['tax_type'] == 'sale' else 1.0

            current_move_info = move_info_dict.setdefault(move_id, {})

            current_move_info['line_name'] = result['move_name']
            current_move_info[column_group_key] = result

            # Apply sign and add values to totals
            totals = total_values_dict[column_group_key]
            for key in number_keys:
                result[key] = sign * result[key]
                totals[key] += result[key]

        lines = []
        for move_id, move_info in move_info_dict.items():
            # 1 line for each move_id
            line = self._create_report_line(report, options, move_info, move_id, number_keys)
            lines.append((0, line))
        # Single total line if only one type of journal is selected
        selected_tax_types = self._vat_book_get_selected_tax_types(options)
        if len(selected_tax_types) < 2:
            total_line = self._create_report_total_line(report, options, total_values_dict)
            lines.append((0, total_line))

        return lines

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        if previous_options is None:
            previous_options = {}

        options['uy_vat_book_tax_types_available'] = {
            'sale': _('Sales'),
            'purchase': _('Purchases'),
            'all': _('All'),
        }
        if options.get('_running_export_test'):
            # Exporting the file is not allowed for 'all'. When executing the export tests, we hence always select 'sales', to avoid raising.
            options['uy_vat_book_tax_type_selected'] = 'sale'
        else:
            options['uy_vat_book_tax_type_selected'] = previous_options.get('uy_vat_book_tax_type_selected', 'all')

    ####################################################
    # REPORT LINES: CORE
    ####################################################

    def _build_query(self, report, options, column_group_key):
        tables, where_clause, where_params = report._query_get(options, 'strict_range')

        where_clause = f"AND {where_clause}"
        tax_types = tuple(self._vat_book_get_selected_tax_types(options))

        return self.env['account.uy.vat.line']._uy_vat_line_build_query(tables, where_clause, where_params, column_group_key, tax_types)

    def _create_report_line(self, report, options, move_vals, move_id, number_values):
        """ Create a standard (non total) line for the report
        :param options: report options
        :param move_vals: values necessary for the line
        :param move_id: id of the account.move (or account.uy.vat.line)
        :param number_values: list of expression_label that require the 'number' class
        """
        columns = []
        for column in options['columns']:
            expression_label = column['expression_label']
            value = move_vals.get(column['column_group_key'], {}).get(expression_label)

            columns.append({
                'name': report.format_value(value, figure_type=column['figure_type']) if value is not None else None,
                'no_format': value,
                'class': 'number' if expression_label in number_values else '',
            })

        return {
            'id': report._get_generic_line_id('account.move', move_id),
            'caret_options': 'account.move',
            'name': move_vals['line_name'],
            'columns': columns,
            'level': 2,
        }

    def _create_report_total_line(self, report, options, total_vals):
        """ Create a total line for the report
        :param options: report options
        :param total_vals: values necessary for the line
        """
        columns = []
        for column in options['columns']:
            expression_label = column['expression_label']
            value = total_vals.get(column['column_group_key'], {}).get(expression_label)

            columns.append({
                'name': report.format_value(value, figure_type=column['figure_type']) if value is not None else None,
                'no_format': value,
                'class': 'number',
            })
        return {
            'id': report._get_generic_line_id(None, None, markup='total'),
            'name': _('Total'),
            'class': 'total',
            'level': 1,
            'columns': columns,
        }

    ####################################################
    # HELPERS
    ####################################################

    def _vat_book_get_selected_tax_types(self, options):
        # If no particular one is selected, then select them all
        selected = options['uy_vat_book_tax_type_selected']
        return ['sale', 'purchase'] if selected == 'all' else [selected]
