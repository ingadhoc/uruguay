# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models
from odoo.tools import SQL


class UruguayanReportCustomHandler(models.AbstractModel):
    _name = "l10n_uy.tax.report.handler"
    _inherit = "account.tax.report.handler"
    _description = "Uruguayan Report Custom Handler"

    def _get_custom_display_config(self):
        parent_config = super()._get_custom_display_config()
        parent_config["templates"]["AccountReportFilters"] = "l10n_uy_reports_ux.L10nUyReportsFiltersCustomizable"
        return parent_config

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        # dict of the form {move_id: {column_group_key: {expression_label: value}}}
        move_info_dict = {}

        # dict of the form {column_group_key: total_value}
        total_values_dict = {}

        # Every key/expression_label that is a number (and should be rendered like one)
        number_keys = ["taxed", "not_taxed", "vat_10", "vat_22", "other_taxes", "total"]

        # Build full query
        query_list = []
        options_per_col_group = report._split_options_per_column_group(options)
        for column_group_key, column_group_options in options_per_col_group.items():
            query = self._build_query(report, column_group_options, column_group_key)
            query_list.append(SQL("(%s)", query))

            # Set defaults here since the results of the query for this column_group_key might be empty
            total_values_dict.setdefault(column_group_key, dict.fromkeys(number_keys, 0.0))

        full_query = SQL(" UNION ALL ").join(query_list)
        self.env.cr.execute(full_query)
        results = self.env.cr.dictfetchall()
        for result in results:
            # Iterate over these results in order to fill the move_info_dict dictionary
            move_id = result["id"]
            column_group_key = result["column_group_key"]

            # For number rendering, take the opposite for sales taxes
            sign = -1.0 if result["tax_type"] == "sale" else 1.0

            current_move_info = move_info_dict.setdefault(move_id, {})

            current_move_info["line_name"] = result["move_name"]
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
        if len(self._vat_book_get_selected_tax_types(options)) < 2:
            lines.append((0, self._create_report_total_line(report, options, total_values_dict)))

        return lines

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options["uy_vat_book_tax_types_available"] = previous_options.get("uy_vat_book_tax_types_available") or {
            "sale": {"name": _("Sales"), "selected": True},
            "purchase": {"name": _("Purchases"), "selected": True},
        }
        if options.get("_running_export_test"):
            # Exporting the file is not allowed for 'purchase'. When executing the export tests, we hence always select 'sales', to avoid raising.
            options["uy_vat_book_tax_types_available"]["purchase"]["selected"] = False

        options["forced_domain"] = [
            *options.get("forced_domain", []),
            ("journal_id.l10n_latam_use_documents", "!=", False),
        ]

        options["custom_display_config"] = {
            "templates": {
                "AccountReportFilters": "l10n_uy_reports_ux.L10nUyTaxReportFiltersCustomizable",
            },
            "components": {
                "AccountReportFilters": "L10nUYTaxReportFilters",
            },
        }

    ####################################################
    # REPORT LINES: CORE
    ####################################################

    def _build_query(self, report, options, column_group_key):
        query = report._get_report_query(options, "strict_range")

        tax_types = tuple(self._vat_book_get_selected_tax_types(options))

        return self.env["account.uy.vat.line"]._uy_vat_line_build_query(
            query.from_clause, query.where_clause, column_group_key, tax_types
        )

    def _create_report_line(self, report, options, move_vals, move_id, number_values):
        """Create a standard (non total) line for the report
        :param options: report options
        :param move_vals: values necessary for the line
        :param move_id: id of the account.move (or account.uy.vat.line)
        :param number_values: list of expression_label that require the 'number' class
        """
        columns = []
        for column in options["columns"]:
            expression_label = column["expression_label"]
            value = move_vals.get(column["column_group_key"], {}).get(expression_label)

            columns.append(report._build_column_dict(value, column, options=options))

        return {
            "id": report._get_generic_line_id("account.move", move_id),
            "caret_options": "account.move",
            "name": move_vals["line_name"],
            "columns": columns,
            "level": 2,
        }

    def _create_report_total_line(self, report, options, total_vals):
        """Create a total line for the report
        :param options: report options
        :param total_vals: values necessary for the line
        """
        columns = []
        for column in options["columns"]:
            expression_label = column["expression_label"]
            value = total_vals.get(column["column_group_key"], {}).get(expression_label)

            columns.append(report._build_column_dict(value, column, options=options))
        return {
            "id": report._get_generic_line_id(None, None, markup="total"),
            "name": _("Total"),
            "class": "total",
            "level": 1,
            "columns": columns,
        }

    ####################################################
    # HELPERS
    ####################################################

    def _vat_book_get_selected_tax_types(self, options):
        # If no particular one is selected, then select them all
        selected_types = [
            selected_type_key
            for selected_type_key, selected_type_value in options["uy_vat_book_tax_types_available"].items()
            if selected_type_value["selected"]
        ]

        return selected_types if selected_types else ["sale", "purchase"]
