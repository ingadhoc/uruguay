from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
import re


_logger = logging.getLogger(__name__)


class ResPartner(models.Model):

    _inherit = 'res.partner'

    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def check_vat(self):
        # EXTENDS: base_vat
        """ Add the validation of other UY document types: CI and NIE """
        ci_nie_types = self.env.ref('l10n_uy_account.it_nie') | self.env.ref('l10n_uy_account.it_ci')
        ci_nie_partners = self.filtered(lambda x: x.vat and x.l10n_latam_identification_type_id in ci_nie_types)
        for partner in ci_nie_partners:
            valid = partner._l10n_uy_check_nie_ci()
            if not valid:
                raise ValidationError(_('Not a valid CI/NIE'))
        return super(ResPartner, self - ci_nie_partners).check_vat()

    def _l10n_uy_check_nie_ci(self):
        """ algorithm to check if a NIE or CI number is a valid one """
        self.ensure_one()
        # Si no tenemos numero de vat entonces es verdadero no hay nada que validar
        if not self.vat:
            return True

        # Si tenemos un numero de vat y este no tiene números entonces no es un numero valido
        ci_nie_number = re.sub('[^0-9]', '', self.vat)
        if not ci_nie_number:
            return False

        # obtenemos el numero a validar y el digito verificador, si es NIE no tomamos en cuenta el primero digito
        is_nie = self.l10n_latam_identification_type_id == self.env.ref('l10n_uy_account.it_nie')
        ci_nie_number, digit_ver = ci_nie_number[1 if is_nie else 0 :-1], int(ci_nie_number[-1])

        # Si el numero es < 7 digitos completamos con 0 a la izquierda
        ci_nie_number = "%07d" % int(ci_nie_number)

        # si el nie supera > 7 digitos no es un nie valido
        if len(ci_nie_number) > 7:
            return False

        random_num = [2, 9, 8, 7, 6, 3, 4]
        sum = 0
        for index, digit in enumerate(ci_nie_number):
            sum += int(digit) * random_num[index]
        res = 10 - (sum % 10)
        if res == 10:
            res = 0
        if res == digit_ver:
            return True
        else:
            return False

    def _is_rut(self):
        """ Check if the partner has a valid RUT """
        self.ensure_one()
        return True if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2' and self.vat else False
