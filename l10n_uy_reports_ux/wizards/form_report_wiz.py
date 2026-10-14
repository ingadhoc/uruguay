import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)

# Payment responsibles billed over this amount, converted to UI at december 31st, go into the form 3150.
L10N_UY_3150_UI_THRESHOLD = 70000

# DGI codes of the document types Sigma accepts on the form 3150: NIE, CI, passport and DNI.
L10N_UY_3150_DOC_CODES = ("1", "3", "5", "6")

# NIE and CI always belong to Uruguay, whatever country the contact has.
L10N_UY_3150_UY_DOC_CODES = ("1", "3")

# Trailing "/1105", "apto 204", "ap. 3" and friends: what is left of the street is the door number.
L10N_UY_UNIT_RE = re.compile(r"(?:\s*/|\s+(?:apto|apt|ap|dpto)\.?)\s*([A-Za-z0-9]{1,4})\s*$", re.IGNORECASE)
L10N_UY_DOOR_RE = re.compile(r"^(.*?)\s+(\d{1,4})$")


class FormReportWiz(models.TransientModel):
    _name = "form.report.wiz"
    _description = "Generate files for Uruguayan Declaration"

    company_id = fields.Many2one("res.company")
    date_from = fields.Date()
    date_to = fields.Date()
    date_period = fields.Char(compute="_compute_date_period")
    uy_form_id = fields.Selection([("2181", "Form 2181"), ("3150", "Form 3150")], "Form", default="2181")
    l10n_uy_form_3102 = fields.Selection(
        [("1", "Yes"), ("2", "No"), ("3", "Not submitted")],
        "Form 3102",
        default="2",
        help="Whether the payment responsibles submitted the form 3102. Reported as is on every record.",
    )
    l10n_uy_warnings = fields.Html(readonly=True)
    res_file = fields.Binary()
    res_filename = fields.Char()

    @api.model
    def default_get(self, list_fields):
        res = super().default_get(list_fields)
        if not res.get("company_id"):
            last_month = fields.Date.subtract(fields.Date.today(), months=1)
            res["company_id"] = self.env.company.id
            res["date_from"] = fields.Date.start_of(last_month, "month")
            res["date_to"] = fields.Date.end_of(last_month, "month")
        return res

    @api.depends("date_to", "date_from")
    def _compute_date_period(self):
        for rec in self:
            rec.date_period = rec.date_to.strftime("%Y%m")

    @api.onchange("uy_form_id")
    def _onchange_uy_form_id(self):
        """The 2181 is filed monthly and the 3150 yearly, so each one starts on a different period"""
        if self.uy_form_id == "3150":
            last_year = fields.Date.subtract(fields.Date.today(), years=1)
            self.date_from = fields.Date.start_of(last_year, "year")
            self.date_to = fields.Date.end_of(last_year, "year")
        else:
            last_month = fields.Date.subtract(fields.Date.today(), months=1)
            self.date_from = fields.Date.start_of(last_month, "month")
            self.date_to = fields.Date.end_of(last_month, "month")

    @api.onchange("date_to", "date_from")
    def _onchange_dates(self):
        """Fix the date to and end to dates given by the user"""
        period = "year" if self.uy_form_id == "3150" else "month"
        self.date_from = fields.Date.start_of(self.date_from, period)
        self.date_to = fields.Date.end_of(self.date_from, period)

    def _get_invoices_domain(self):
        """Devuelve el dominio a utilizar para obtener las facturas que seran
        mostradas en el archivo del formulario.
        """
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("move_type", "!=", "entry"),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("partner_id.vat", "!=", False),
            ("l10n_latam_document_type_id.code", "!=", "0"),
            ("l10n_latam_document_type_id.code", "!=", False),
            ("l10n_latam_document_type_id.code", "not in", ["121", "122", "123", "124", "221", "222", "223", "224"]),
        ]

        if self._l10n_uy_edi_installed():
            domain += ["|", ("l10n_uy_edi_cfe_state", "in", ["accepted"]), ("move_type", "like", "in_")]
        return domain

    def _l10n_uy_edi_installed(self):
        return self.sudo().env["ir.module.module"].search([("name", "=", "l10n_uy_edi")], limit=1).state in (
            "installed",
            "to install",
            "to upgrade",
        )

    def _get_invoices(self):
        """Both customer and vendor bills

        * Solo debemos tomar en cuenta los cfe que tengan un partner con numero de identificacion, los que no no tenemos
          que tomarlos en cuenta ni enviar nada.
        * Solo tomar en cuenta los aceptados, el resto no
        """
        self.ensure_one()
        domain = self._get_invoices_domain()
        res = self.env["account.move"].search(domain, order="invoice_date asc, name asc, id asc")
        return res

    def _search_tax(self, tax_amount, tax_type):
        res = (
            self.env["account.tax"]
            .with_context(active_test=False)
            .search(
                [
                    ("type_tax_use", "=", tax_type),
                    ("company_id", "=", self.company_id.id),
                    ("amount", "=", tax_amount),
                    ("l10n_uy_tax_category", "=", "vat"),
                ],
                limit=1,
            )
        )
        return res

    def _get_form_2181_data(self):
        """
        Prepara the content of the file

        Este es un solo archivo TXT el cual contiene.
        En el Rubro 5 se ingresan agrupados por Identificación del contribuyente y número de línea
        correspondiente al concepto declarado e importe.

        Agrupado por partner, por periodo y fecha de factura la información de los impuestos generados

        Devuelve un string con las lineas de la carpeta a escribir
        """
        lines = []

        # Importante: el archivo generado mezcla iva compras e iva ventas.
        line_code = {
            self._search_tax(22.0, "sale"): "502",  # 502 IVA Ventas Tasa Básica a Contribuyentes
            self._search_tax(10.0, "sale"): "503",  # 503 IVA Ventas Tasa Mínima a Contribuyentes
            self._search_tax(0.0, "purchase"): "504",  # Compras Plaza Exentas de IVA
            self._search_tax(22.0, "purchase"): "505",  # 505 IVA Compras Plaza Tasa Básica
            self._search_tax(10.0, "purchase"): "506",  # 506 IVA Compras Plaza Tasa Mínima
        }
        # Estos dos parece que tambien van pero no tenemos un impuestos para colocarlo
        # ("507", "507	- IVA Ventas tasa 10% a Contribuyentes"),
        # ("508", "508	- IVA Compras Plaza Tasa 10%"),

        taxes_raw = list(line_code.keys())
        taxes = self.env["account.tax"]
        for item in taxes_raw:
            taxes |= item

        tax_code = {}
        taxes_group_ids = taxes.mapped("tax_group_id").ids
        for tax in taxes:
            tax_code[(tax.tax_group_id.id, tax.type_tax_use)] = line_code.get(tax)

        invoices = self._get_invoices()

        # Revisando que todos los impuestos esten bien configurados
        error = ""
        for line in invoices.line_ids:
            if line.tax_ids and line.tax_ids not in taxes:
                error += "\n- %s %s" % (line.tax_ids.mapped("name"), line.move_id.display_name)
        if error:
            _logger.warning("No se puede generar declaracion de impuestos (config impuesto) para %s" % error)

        # TODO KZ: Agrupamos por RUT pero sin tener en cuenta si no fue enviado el receptor entonces no se debe tomar en cuenta para el total)
        # Ejemplo un e-tTicket con monto pequeño de monto total. de lado de Odoo esta registrado para el Partner ABC.
        # Pero al final esa factura se envia sin datos del receptor a Uruware y DGI y no e reporta a DGI no se tiene que
        # informar. es por eso que debemos saltarlo aca. Intente consultado _uy_cfe_A_receptor
        # pero tenemos un problema. cuando se genera desde uruware no tenemos este dato. ver de mejorar
        data = {}
        for inv in invoices:
            # temp = inv._uy_cfe_A_receptor()
            # if not temp:
            #    continue
            if inv.partner_id.vat in data:
                data[inv.partner_id.vat] |= inv
            else:
                data[inv.partner_id.vat] = inv

        for rut_partner, invoices in data.items():
            amount_total = {}
            for inv in invoices:
                subtotals = inv.tax_totals.get("subtotals", [])
                is_sale = "out_" in inv.move_type
                sign = 1 if inv.move_type in ["out_invoice", "in_invoice", "out_receipt", "in_receipt"] else -1

                for item in subtotals:
                    tax_group_ids = item.get("tax_groups", [])
                    for tax_group_id in tax_group_ids:
                        tax_amount = tax_group_id.get("tax_amount")
                        tax_id = tax_group_id["id"]
                        if tax_id in taxes_group_ids:
                            key = (tax_id, "sale" if is_sale else "purchase")
                            amount_total[key] = amount_total.get(key, 0.0) + (sign * tax_amount)

            for tax in amount_total:
                if not tax_code.get(tax):
                    continue

                # Campo 1 - RUT Informante. Num 12 (Si <12 dígitos completa con 0 a la izq)
                if self.company_id.vat:
                    content_data = self.company_id.vat.zfill(12) + ";"
                else:
                    raise UserError(_("Please configure a Tax ID number for your company"))

                # Campo 2 - Formulario. Num 5
                content_data += f"{int(self.uy_form_id):05d};"

                # Campo 3 - Período (AAAAMM) Num 6. Ejemplo: 202406
                content_data += f"{self.date_period};"

                # Campo 4 - RUT Informado. Num 12
                content_data += rut_partner.zfill(12) + ";"

                # Campo 5 - Factura AAAAMM Num 6. Ejemplo: 202405
                content_data += "{};".format(line.move_id.date.strftime("%Y%m"))

                # Campo 6 - Línea del Rubro 5 del Formulario
                content_data += f"{tax_code.get(tax)};"

                # Campo 7 - Importe. Num 12. Ejemplo: 2750 ó -2750
                amount = int(round(amount_total.get(tax, 0)))
                content_data += f"{amount};"

                lines.append(content_data)

        res = "\n".join(lines)
        return res

    # Form 3150 - Declaración de instituciones de enseñanza privada

    def _get_form_3150_invoices(self):
        """Customer invoices and credit notes of the year, whether they were paid or not"""
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("state", "=", "posted"),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("invoice_date", ">=", self.date_from),
            ("invoice_date", "<=", self.date_to),
        ]
        if self._l10n_uy_edi_installed():
            domain.append(("l10n_uy_edi_cfe_state", "=", "accepted"))
        return self.env["account.move"].search(domain)

    def _get_form_3150_persons(self, moves):
        """How many people the payment responsible is informing for.

        The localization has no way to know, so it reports one. The Academic bridge counts the students.
        """
        return 1

    def _l10n_uy_split_street(self, street):
        """Split the free text street of a contact into the street, door and unit the file needs.

        Returns the three parts plus the list of problems found while splitting.
        """
        rest = (street or "").strip()
        unit = ""
        problems = []

        match = L10N_UY_UNIT_RE.search(rest)
        if match:
            unit = match.group(1)
            rest = rest[: match.start()].strip()

        door = ""
        match = L10N_UY_DOOR_RE.match(rest)
        if match:
            door = match.group(2)
            rest = match.group(1).strip()
            if len(rest.split()) < 2:
                problems.append(_("the door number cannot be told apart from the street name"))
        else:
            problems.append(_("no door number could be read from the address"))

        if len(rest) < 3:
            problems.append(_("the street has less than 3 characters"))

        return rest[:35], door, unit, problems

    def _get_form_3150_partner_problems(self, partner, moves):
        """What Sigma would reject about this payment responsible, in plain words"""
        problems = []
        doc_code = partner.l10n_latam_identification_type_id.l10n_uy_dgi_code
        vat = re.sub(r"\D", "", partner.vat or "")

        if not vat:
            problems.append(_("it has no identification number"))
        elif len(vat) > 12:
            problems.append(_("its identification number has more than 12 digits"))
        if doc_code not in L10N_UY_3150_DOC_CODES:
            problems.append(_("its document type is not CI, NIE, DNI nor passport"))
        elif doc_code not in L10N_UY_3150_UY_DOC_CODES and not partner.country_id:
            problems.append(_("it has no country, and its document type does not imply one"))
        if len((partner.name or "").strip()) < 3:
            problems.append(_("its name has less than 3 characters"))

        problems += self._l10n_uy_split_street(partner.street)[3]
        return problems

    def _get_form_3150_root(self, partner, line):
        """Characters 1 to 40, repeated at the beginning of the five lines of every record"""
        doc_code = partner.l10n_latam_identification_type_id.l10n_uy_dgi_code or ""
        country_code = partner.country_id.code or ""
        if doc_code in L10N_UY_3150_UY_DOC_CODES:
            country_code = "UY"
        return "".join(
            [
                re.sub(r"\D", "", self.company_id.vat or "").zfill(12),
                "3150",
                self.date_period,
                doc_code.zfill(2),
                re.sub(r"\D", "", partner.vat or "").zfill(12),
                country_code.ljust(2),
                line,
                ";",
            ]
        )

    def _get_form_3150_data(self):
        """Five lines per payment responsible billed over the threshold during the year.

        Returns the content of the file. The problems found are left on l10n_uy_warnings, they do not stop
        the download: Sigma imports the valid records and reports the rest.
        """
        self.ensure_one()
        company = self.company_id

        if not company.vat:
            raise UserError(_("Please configure a Tax ID number for your company"))
        if not company.l10n_uy_dgi_department_code or not company.l10n_uy_dgi_locality_code:
            raise UserError(
                _("Please configure the DGI department and locality codes in the settings of %s", company.name)
            )

        ui_currency = self.env.ref("base.UYI")
        if not self.env["res.currency.rate"].search_count(
            [
                ("currency_id", "=", ui_currency.id),
                ("name", "=", self.date_to),
                ("company_id", "in", (False, company.root_id.id)),
            ],
            limit=1,
        ):
            raise UserError(
                _(
                    "There is no UI (Unidad Indexada) rate for %(date)s. Load it before generating the file,"
                    " the threshold of the declaration is measured in UI.",
                    date=self.date_to,
                )
            )

        moves_per_partner = {}
        for move in self._get_form_3150_invoices():
            partner = move.commercial_partner_id
            moves_per_partner[partner] = moves_per_partner.get(partner, self.env["account.move"]) | move

        lines = []
        problems = []
        for partner, moves in sorted(moves_per_partner.items(), key=lambda item: (item[0].name or "").lower()):
            amount = int(round(sum(moves.mapped("amount_total_signed"))))
            amount_ui = company.currency_id._convert(amount, ui_currency, company, self.date_to)
            if float_compare(amount_ui, L10N_UY_3150_UI_THRESHOLD, precision_rounding=ui_currency.rounding) <= 0:
                continue

            partner_problems = self._get_form_3150_partner_problems(partner, moves)
            if partner_problems:
                problems.append((partner, partner_problems))

            street, door, unit = self._l10n_uy_split_street(partner.street)[:3]
            lines.append(self._get_form_3150_root(partner, "A") + (partner.name or "")[:35])
            lines.append(
                self._get_form_3150_root(partner, "B")
                + f"{company.l10n_uy_dgi_department_code};{company.l10n_uy_dgi_locality_code}"
            )
            lines.append(self._get_form_3150_root(partner, "C") + street)
            lines.append(self._get_form_3150_root(partner, "D"))
            lines.append(
                self._get_form_3150_root(partner, "E")
                + ";".join(
                    [
                        door.zfill(4) if door else "S/N",
                        unit.zfill(4) if unit.isdigit() else (unit[:4].ljust(4) if unit else "0000"),
                        str(amount).zfill(12),
                        "A",
                        "12",
                        self.l10n_uy_form_3102,
                        str(self._get_form_3150_persons(moves)).zfill(4),
                    ]
                )
            )

        self.l10n_uy_warnings = self._l10n_uy_render_problems(problems)
        return "\r\n".join(lines) + "\r\n" if lines else ""

    def _l10n_uy_render_problems(self, problems):
        """One line per payment responsible, linking the contact so that someone can go and fix it"""
        if not problems:
            return False
        items = [
            "<li><a href='/odoo/res.partner/%s'>%s</a>: %s</li>"
            % (partner.id, partner.display_name, ", ".join(reasons))
            for partner, reasons in problems
        ]
        return "<p>%s</p><ul>%s</ul>" % (
            _("Sigma may reject these payment responsibles. You can download the file anyway."),
            "".join(items),
        )

    def _get_res_filename(self):
        if self.uy_form_id == "3150":
            return "3150_%s.txt" % self.date_to.year
        # TODO No sabemos realmente cual es el formato, solo tomamos de ejemplo el que genera uruware
        # Ejemplo SumiFormulario2-181DGI_10_2022.txt ver de mejorarlo del periodo
        return self.company_id.name[:4] + "Formulario2-181DGI_" + self.date_period[-2:] + self.date_period[:4] + ".txt"

    def action_get_files(self):
        """Button that will generate the files for the selected options given"""
        self.ensure_one()

        if self.company_id.country_id.code != "UY":
            raise UserError(_("This report can only be generated for Uruguayan companies"))

        self.l10n_uy_warnings = False
        data = getattr(self, "_get_form_%s_data" % self.uy_form_id)() if self.uy_form_id else None
        if data:
            self.res_filename = self._get_res_filename()
            self.res_file = base64.encodebytes(data.encode("ISO-8859-1", errors="replace"))
        else:
            self.res_filename = _("No file was generated")
            self.res_file = False

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
