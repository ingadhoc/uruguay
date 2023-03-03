from odoo.tests import common
from odoo.exceptions import ValidationError


class CheckUyVat(common.TransactionCase):

    @classmethod
    def _test_uy_create_partner(self, identification_type, vat):
        return self.env['res.partner'].create({
            'name': 'Partner uruguayo',
            'l10n_latam_identification_type_id': self.env.ref(f'l10n_uy_account.{identification_type}').id,
            'vat': vat,
        })

    def test_01_uy_nie_invalid_vat(self):
        # Invalid nie
        with self.assertRaisesRegex(ValidationError, 'Not a valid CI/NIE'):
            partner = self._test_uy_create_partner('it_nie', '93:402.010-2')

    def test_02_uy_ci_valid_vat(self):
        # Valid nie
        partner = self._test_uy_create_partner('it_nie', '93:402.010-1')
        self.assertEqual(partner._l10n_uy_check_nie_ci(), True)

    def test_03_uy_ci_invalid_vat(self):
        # Invalid CI
        with self.assertRaisesRegex(ValidationError, 'Not a valid CI/NIE'):
            self._test_uy_create_partner('it_ci', '3:402.010-2')

    def test_04_uy_ci_valid_vat(self):
        # Valid CI
        partner = self._test_uy_create_partner('it_ci', '3:402.010-1')
        self.assertEqual(partner._l10n_uy_check_nie_ci(), True)

    def test_05_uy_rut_invalid_vat(self):
        # Invalid RUT
        with self.assertRaisesRegex(ValidationError, 'Not a valid RUT/RUC'):
            partner = self._test_uy_create_partner('it_rut', '215521750018')

    def test_06_uy_rut_valid_vat(self):
        # Valid RUT
        partner = self._test_uy_create_partner('it_rut', '215521750017')
        self.assertEqual(partner._is_rut(), True)
