from odoo.tests import common
from odoo.exceptions import ValidationError


class CheckUyVat(common.TransactionCase):

   def setUp(self):

       # Válidos
       self.NIE = "93:402.010-1"
       self.CI = "3:402.010-1"
       self.RUT = "215521750017"

       super().setUp()

   def test_uy_vat(self):
       """ Check vat uruguay partner """

       partner = self.env['res.partner'].create({
           'name': 'Partner uruguayo',
           'vat': self.NIE,
           'l10n_latam_identification_type_id': self.env.ref('l10n_uy_account.it_nie').id,
       })

       # NIE Válido
       self.assertEqual(self.NIE, partner.vat)

       # NIE Inválido
       with self.assertRaisesRegex(ValidationError, 'Not a valid CI/NIE'):
           partner.vat = "93:401052-2"

       self.assertEqual(1, 2)