from odoo import models, api, _
from odoo.exceptions import ValidationError
import logging
import re


_logger = logging.getLogger(__name__)


class ResPartner(models.Model):

    _inherit = 'res.partner'

    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def check_vat(self):
        """ Uruguayan VAT validation. : Add validation of Uruguayan RUT removing the logic of odoo that requires prefix
        of the contry code CC## in the vat number

        Also add the validation of UY document types RUC/RUT (vat), CI and NIE

        TODO This need to be moved to module base_vat with name check_vat_uy when adding to Odoo Official """
        # NOTE by the moment we include the RUT (VAT UY) validation also here because we extend the messages
        # errors to be more friendly to the user. In a future when Odoo improve the base_vat message errors
        # we can change this method and use the base_vat.check_vat_uy method.
        l10n_uy_partners = self.filtered(lambda x: x.l10n_latam_identification_type_id.l10n_uy_dgi_code)
        for partner in l10n_uy_partners:
            msg = partner._l10n_uy_check_document_number_error()
            if msg:
                raise ValidationError(msg)
        return super(ResPartner, self - l10n_uy_partners).check_vat()

    @api.onchange('vat')
    def _onchange_document_number(self):
        msg = self._l10n_uy_check_document_number_error()
        if msg:
            return {'warning': {'title': "Warning", 'message': msg, 'type': 'notification'}}

    def _l10n_uy_check_document_number_error(self):
        """ Return False if everything ok, return a message if there is an error in the doc number """
        self.ensure_one()
        if not self.vat:
            return False
        msg = False
        if self.l10n_latam_identification_type_id.is_vat:
            valid, msg = self._l10n_uy_check_ruc_rut(self.vat)
            if not valid:
                msg = _('Not a valid RUT/RUC: %s') % msg
        ci_nie_types = self.env.ref('l10n_uy_account.it_nie') | self.env.ref('l10n_uy_account.it_ci')
        if self.l10n_latam_identification_type_id in ci_nie_types:
            valid = self._l10n_uy_check_nie_ci()
            if not valid:
                msg = _('Not a valid CI/NIE')
        return msg

    @api.model
    def _l10n_uy_check_ruc_rut(self, vat):
        """ Check if the VAT is valid if. Return tuple:
            (True, False)   if valid vat number
            (False, msg)    if NOT valid number, and the msg with the error
        """
        if not self.vat:
            return True, False

        msg = False
        try:
            import stdnum.uy
            module = stdnum.uy.rut
            res = None
        except ImportError:
            _logger.info("Uruguayan VAT was not validated because stdnum.uy module is not available")
            return True, False
        try:
            res = module.validate(vat)
        except module.InvalidChecksum:
            msg = _('The validation digit is not valid for "%s"') % self.l10n_latam_identification_type_id.name
        except module.InvalidLength:
            msg = _('Invalid length for "%s"') % self.l10n_latam_identification_type_id.name
        except module.InvalidFormat:
            msg = _('Only numbers allowed for "%s"') % self.l10n_latam_identification_type_id.name
        except Exception as error:
            msg = repr(error)
        return bool(res), msg

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

        # Si el numero es < 7 digitos completamos con 0 a la derecha
        ci_nie_number = "%07d" % int(ci_nie_number)

        random_num = [2, 9, 8, 7, 6, 3, 4, 5]
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
