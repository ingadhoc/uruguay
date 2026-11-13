##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64
from datetime import date

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install_l10n", "post_install", "-at_install")
class TestForm3150(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country("uy")
    def setUpClass(cls):
        super().setUpClass()

        # The EDI filter is tested by the 2181 and needs an l10n_uy_edi.document we do not want to fake here.
        cls.classPatch(type(cls.env["form.report.wiz"]), "_l10n_uy_edi_installed", lambda self: False)

        # The declaration is filed over the previous calendar year
        cls.year = fields.Date.today().year - 1
        cls.date_from = date(cls.year, 1, 1)
        cls.date_to = date(cls.year, 12, 31)
        cls.invoice_date = date(cls.year, 6, 15)

        cls.company = cls.company_data["company"]
        cls.company.sudo().write(
            {
                "vat": "214164660014",
                "l10n_uy_dgi_department_code": "V",
                "l10n_uy_dgi_locality_code": "AA",
            }
        )

        cls.uyi = cls.env.ref("base.UYI")
        cls.uyi.active = True
        cls.env["res.currency.rate"].sudo().search([("currency_id", "=", cls.uyi.id)]).unlink()
        # 1 UI = 10 UYU, so the 70.000 UI threshold of the declaration is 700.000 UYU
        cls.env["res.currency.rate"].create(
            {
                "name": cls.date_to,
                "currency_id": cls.uyi.id,
                "company_id": cls.company.id,
                "rate": 0.1,
            }
        )

        cls.doc_invoice = cls.env.ref("l10n_uy.dc_e_inv")
        cls.doc_credit_note = cls.env.ref("l10n_uy.dc_cn_e_inv")

        cls.over = cls._create_responsible("Perez Juan", "34020101", "Carlos Quijano 1089")
        cls.exact = cls._create_responsible("Silva Ana", "12345672", "Mariano Moreno 2266 apto 204")
        cls.just_over = cls._create_responsible("Techera Luis", "45678905", "Rambla Republica Argentina 1225 /1105")
        cls.just_under = cls._create_responsible("Suarez Pedro", "33333333", "Rio Negro 1370")
        cls.under = cls._create_responsible("Vega Marta", "55555555", "Colonia 1479")

        cls._create_move(cls.over, 900000)
        cls._create_move(cls.over, 100000, move_type="out_refund")
        cls._create_move(cls.exact, 700000)
        cls._create_move(cls.just_over, 700010)
        cls._create_move(cls.just_under, 699990)
        cls._create_move(cls.under, 500000)
        # Out of the period, it must not be taken into account
        cls._create_move(cls.under, 900000, invoice_date=date(cls.year - 1, 12, 15))

    @classmethod
    def _create_responsible(cls, name, vat, street, **values):
        return cls.env["res.partner"].create(
            {
                "name": name,
                "vat": vat,
                "street": street,
                "l10n_latam_identification_type_id": cls.env.ref("l10n_uy.it_ci").id,
                "country_id": cls.env.ref("base.uy").id,
                **values,
            }
        )

    @classmethod
    def _create_move(cls, partner, amount, move_type="out_invoice", invoice_date=None, taxes=None, **values):
        doc_type = cls.doc_credit_note if move_type == "out_refund" else cls.doc_invoice
        move = cls._create_invoice(
            move_type=move_type,
            partner_id=partner.id,
            invoice_date=invoice_date or cls.invoice_date,
            l10n_latam_document_type_id=doc_type.id,
            invoice_line_ids=[
                Command.create(
                    {
                        "name": "Cuota",
                        "quantity": 1,
                        "price_unit": amount,
                        "tax_ids": [Command.set((taxes or cls.env["account.tax"]).ids)],
                    }
                )
            ],
            **values,
        )
        # l10n_uy_ux sends the CFE to DGI on post and rolls the move back to draft when it fails,
        # and a test database has no Uruware account. The context is ignored when it is not installed.
        move.with_context(l10n_uy_skip_edi_send=True).action_post()
        return move

    def _get_wizard(self, **values):
        return self.env["form.report.wiz"].create(
            {
                "company_id": self.company.id,
                "uy_form_id": "3150",
                "date_from": self.date_from,
                "date_to": self.date_to,
                **values,
            }
        )

    def _get_file(self, wizard):
        wizard.action_get_files()
        if not wizard.res_file:
            return ""
        return base64.b64decode(wizard.res_file).decode("ISO-8859-1")

    def _records(self, content):
        """The file lines grouped by payment responsible, in the order they were written"""
        lines = content.split("\r\n")[:-1]
        return [lines[index : index + 5] for index in range(0, len(lines), 5)]

    def _record_of(self, content, name):
        """The five lines of the record that reports this name on its line A"""
        for record in self._records(content):
            if record[0][40:] == name:
                return record
        raise AssertionError("There is no record for %r in %r" % (name, content))

    # Splitting the street

    def test_split_street(self):
        wizard = self._get_wizard()
        cases = [
            ("Carlos quijano 1089", ("Carlos quijano", "1089", ""), False),
            ("Mariano Moreno 2266 apto 204", ("Mariano Moreno", "2266", "204"), False),
            ("Rambla República Argentina 1225 /1105", ("Rambla República Argentina", "1225", "1105"), False),
            ("Dr. Lauro Muller 1964 Ap. 12", ("Dr. Lauro Muller", "1964", "12"), False),
            # The door cannot be read, everything stays on the street
            ("Carlos Suárez Lerena m34 s11", ("Carlos Suárez Lerena m34 s11", "", ""), True),
            ("18 de Julio", ("18 de Julio", "", ""), True),
            ("", ("", "", ""), True),
            # A single word before the number is most likely a street name ending in a number
            ("Ruta 8", ("Ruta", "8", ""), True),
            # What is left is shorter than the 3 characters Sigma asks for
            ("Yi 1507", ("Yi", "1507", ""), True),
        ]
        for street, expected, has_problems in cases:
            with self.subTest(street=street):
                result = wizard._l10n_uy_split_street(street)
                self.assertEqual(result[:3], expected)
                self.assertEqual(bool(result[3]), has_problems)

    # The file itself

    def test_file_content(self):
        content = self._get_file(self._get_wizard())
        records = self._records(content)

        # Only the two responsibles over 70.000 UI, sorted by name
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0][0][40:], "Perez Juan")
        self.assertEqual(records[1][0][40:], "Techera Luis")

        root = records[0][0][:40]
        self.assertEqual(root[0:12], "214164660014")  # RUT of the company
        self.assertEqual(root[12:16], "3150")
        self.assertEqual(root[16:22], "%s12" % self.year)
        self.assertEqual(root[22:24], "03")  # CI
        self.assertEqual(root[24:36], "000034020101")
        self.assertEqual(root[36:38], "UY")
        self.assertEqual(root[38:40], "A;")

        # The same root opens the five lines of the record
        self.assertEqual([line[38] for line in records[0]], ["A", "B", "C", "D", "E"])
        for line in records[0]:
            self.assertEqual(line[:38], root[:38])

        self.assertEqual(records[0][1][40:], "V;AA")
        self.assertEqual(records[0][2][40:], "Carlos Quijano")
        self.assertEqual(records[0][3][40:], "")
        # 900.000 billed less the 100.000 credit note
        self.assertEqual(records[0][4][40:], "1089;0000;000000800000;A;12;2;0001")

        self.assertEqual(records[1][4][40:], "1225;1105;000000700010;A;12;2;0001")

        self.assertTrue(content.endswith("\r\n"))
        self.assertEqual(self._get_wizard()._get_res_filename(), "3150_%s.txt" % self.year)

    def test_threshold(self):
        """Exactly 70.000 UI is not over the threshold, ten pesos more are and ten pesos less are not"""
        content = self._get_file(self._get_wizard())
        self.assertNotIn("Silva Ana", content)
        self.assertIn("Techera Luis", content)
        self.assertNotIn("Suarez Pedro", content)
        self.assertNotIn("Vega Marta", content)

    def test_the_amount_includes_the_taxes(self):
        """Exactly 70.000 UI without taxes stays out of the file, the same amount plus its VAT goes in"""
        partner = self._create_responsible("Ramos Elena", "22222222", "Ejido 1495")
        move = self._create_move(partner, 700000, taxes=self.tax_sale_a)
        self.assertGreater(move.amount_total_signed, 700000, "the move has to carry a tax")

        record = self._record_of(self._get_file(self._get_wizard()), "Ramos Elena")
        self.assertEqual(record[4][40:].split(";")[2], str(int(round(move.amount_total_signed))).zfill(12))

    def test_form_3102(self):
        content = self._get_file(self._get_wizard(l10n_uy_form_3102="1"))
        self.assertEqual(self._records(content)[0][4][40:], "1089;0000;000000800000;A;12;1;0001")

    def test_period_is_yearly(self):
        wizard = self._get_wizard(uy_form_id="2181")
        wizard.uy_form_id = "3150"
        wizard._onchange_uy_form_id()
        self.assertEqual(wizard.date_from.month, 1)
        self.assertEqual(wizard.date_from.day, 1)
        self.assertEqual(wizard.date_to.month, 12)
        self.assertEqual(wizard.date_to.day, 31)
        self.assertEqual(wizard.date_from.year, wizard.date_to.year)

    def test_period_is_forced_to_the_whole_year(self):
        """A wizard built by code with any other range still writes the file of the year of date_to"""
        wizard = self._get_wizard(date_from=date(self.year, 3, 1), date_to=date(self.year, 7, 31))
        content = self._get_file(wizard)

        self.assertEqual(wizard.date_from, self.date_from)
        self.assertEqual(wizard.date_to, self.date_to)
        self.assertEqual(self._records(content)[0][0][16:22], "%s12" % self.year)
        self.assertEqual(wizard.res_filename, "3150_%s.txt" % self.year)

    def test_accents_travel_in_the_file(self):
        self.over.write({"name": "Núñez Martín", "street": "Soriano 1180"})
        record = self._record_of(self._get_file(self._get_wizard()), "Núñez Martín")
        self.assertEqual(record[2][40:], "Soriano")

    def test_characters_outside_the_charset_are_reported(self):
        """The file is written in ISO-8859-1, what does not fit in it is a problem of the contact"""
        self.over.name = "Nagy Erzsébet Ő"
        wizard = self._get_wizard()

        record = self._record_of(self._get_file(wizard), "Nagy Erzsébet O")
        self.assertEqual(record[0][38], "A")
        self.assertIn("/odoo/res.partner/%s" % self.over.id, wizard.l10n_uy_warnings)

    def test_separators_inside_the_name(self):
        """A ";" or a line break inside the name would cut the record of the file in two"""
        self.over.name = "Perez; Juan\nCarlos"
        self._record_of(self._get_file(self._get_wizard()), "Perez Juan Carlos")

    def test_long_name_is_cut_and_reported(self):
        self.over.name = "Perez Rodriguez Fernandez de la Cruz Juan Carlos"
        wizard = self._get_wizard()

        self._record_of(self._get_file(wizard), self.over.name[:35])
        self.assertIn("/odoo/res.partner/%s" % self.over.id, wizard.l10n_uy_warnings)

    def test_identification_with_letters_is_reported(self):
        """Sigma only takes digits, so a passport with letters is not reported as it is written on the contact"""
        self.over.write(
            {
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_pass").id,
                "vat": "AB123456",
            }
        )
        wizard = self._get_wizard()

        record = self._record_of(self._get_file(wizard), "Perez Juan")
        self.assertEqual(record[0][24:36], "000000123456")
        self.assertIn("/odoo/res.partner/%s" % self.over.id, wizard.l10n_uy_warnings)

    def test_foreign_document_keeps_its_country(self):
        """CI and NIE always go as uruguayan, the rest report the country of the contact"""
        self.over.write(
            {
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_dni").id,
                "vat": "12345678",
                "country_id": self.env.ref("base.ar").id,
            }
        )
        record = self._record_of(self._get_file(self._get_wizard()), "Perez Juan")
        self.assertEqual(record[0][22:24], "06")  # DNI
        self.assertEqual(record[0][36:38], "AR")

    def test_edi_filter(self):
        """With l10n_uy_edi installed only the CFE the DGI accepted are reported"""
        wizard = self._get_wizard()
        cfe_accepted = ("l10n_uy_edi_cfe_state", "=", "accepted")
        self.assertNotIn(cfe_accepted, wizard._get_form_3150_invoices_domain())

        self.patch(type(wizard), "_l10n_uy_edi_installed", lambda self: True)
        self.assertIn(cfe_accepted, wizard._get_form_3150_invoices_domain())

    # What the wizard refuses to do

    def test_non_uruguayan_company(self):
        argentina = self.env.ref("base.ar")
        argentina.currency_id.active = True
        company = self.env["res.company"].create(
            {
                "name": "Not Uruguayan",
                "country_id": argentina.id,
                "currency_id": argentina.currency_id.id,
            }
        )
        wizard = self._get_wizard(company_id=company.id)
        with self.assertRaisesRegex(UserError, "only be generated for Uruguayan companies"):
            wizard.action_get_files()

    def test_company_currency_is_not_uyu(self):
        """The amounts of the file are uruguayan pesos: there is nothing to report from another currency"""
        dollar = self.env.ref("base.USD")
        dollar.active = True
        company = self.env["res.company"].create(
            {
                "name": "Colegio en dolares",
                "country_id": self.env.ref("base.uy").id,
                "currency_id": dollar.id,
                "vat": "214164660014",
            }
        )
        wizard = self._get_wizard(company_id=company.id)
        with self.assertRaisesRegex(UserError, "uruguayan pesos"):
            wizard.action_get_files()

    def test_missing_ui_rate(self):
        wizard = self._get_wizard()
        self.env["res.currency.rate"].sudo().search([("currency_id", "=", self.uyi.id)]).unlink()
        with self.assertRaisesRegex(UserError, "no UI"):
            wizard.action_get_files()

    def test_missing_dgi_codes(self):
        self.company.l10n_uy_dgi_locality_code = False
        with self.assertRaisesRegex(UserError, "DGI department and locality codes"):
            self._get_wizard().action_get_files()

    # The list of problems

    def test_problems_do_not_block(self):
        self.over.write({"vat": False, "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_other").id})
        wizard = self._get_wizard()
        content = self._get_file(wizard)

        self.assertIn("Perez Juan", content, "The file is generated anyway")
        self.assertIn("Perez Juan", wizard.l10n_uy_warnings)
        self.assertIn("/odoo/res.partner/%s" % self.over.id, wizard.l10n_uy_warnings)

    def test_address_that_cannot_be_split_is_listed(self):
        self.over.street = "18 de Julio"
        wizard = self._get_wizard()
        self._get_file(wizard)

        self.assertIn("/odoo/res.partner/%s" % self.over.id, wizard.l10n_uy_warnings)

    def test_a_clean_responsible_adds_no_problem(self):
        """Breaking the address of a responsible that had nothing to fix adds exactly one problem.

        It is measured as a difference so that the test does not depend on the problems other modules
        add to the list, as the Academic bridge does with the students.
        """
        wizard = self._get_wizard()
        moves = self.env["account.move"].search([("partner_id", "=", self.over.id)])

        before = wizard._get_form_3150_partner_problems(self.over, moves)
        self.over.street = "18 de Julio"
        after = wizard._get_form_3150_partner_problems(self.over, moves)
        self.assertEqual(len(after), len(before) + 1, after)
