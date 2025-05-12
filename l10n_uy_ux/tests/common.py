from unittest import mock

import requests
from odoo.addons.l10n_uy_edi.tests.common import TestUyEdi
from odoo.tools import misc


class TestUyEdiL10nUyUx(TestUyEdi):
    def _mocked_response(self, response_file, exception=None):
        """Read the xml response file, change it to dictionary and return the result. We replace the original method
        from l10n_uy_edi because here we add tests with a different root l10n_uy_ux/tests/responses/ for files."""
        if response_file == "NO_RESPONSE" or not response_file:
            mock_response = None
        else:
            xml_content = misc.file_open("l10n_uy_ux/tests/responses/" + response_file + ".xml", mode="rb").read()
            mock_response = mock.Mock(spec=requests.Response)
            mock_response.status_code = 200
            mock_response.headers = ""
            mock_response.content = xml_content
        errors = [exception] if exception else []
        return self.env["l10n_uy_edi.document"]._process_response(mock_response, errors)

    def _create_uy_partner(self, partner_name, vat):
        """Create a partner with the required fields for the test."""
        return self.env["res.partner"].create(
            {
                "name": partner_name,
                "l10n_latam_identification_type_id": self.env.ref("l10n_uy.it_rut").id,
                "vat": vat,
                "street": "Guatemala 1075 (11800)",
                "city": "Montevideo",
                "state_id": self.env.ref("base.state_uy_10").id,
                "country_id": self.env.ref("base.uy").id,
            }
        )

    def _search_account_liability_payable(self, code):
        """Search for an account with an specific code."""
        return self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company_uy.id),
                ("account_type", "=", "liability_payable"),
                ("code", "=", code),
            ],
            limit=1,
        )
