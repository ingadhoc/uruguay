from odoo import models, api
import stdnum.uy


class ResPartner(models.Model):

    _inherit = 'res.partner'

    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def check_vat(self):
        """ Add validation of uruguayan RUT removing the logic of odoo that requires prefix of the contry code CC## in
        the vat number """
        # NOTE by the moment we include the RUT (VAT UY) validation also here because we extend the messages
        # errors to be more friendly to the user. In a future when Odoo improve the base_vat message errors
        # we can change this method and use the base_vat.check_vat_uy method.
        l10n_uy_partners = self.filtered(lambda x: x.l10n_latam_identification_type_id.l10n_uy_dgi_code)
        for partner in l10n_uy_partners.filtered(lambda x: x.vat and x.l10n_latam_identification_type_id.is_vat):
            partner.l10n_uy_check_vat(partner.vat)
        return super(ResPartner, self - l10n_uy_partners).check_vat()

    def l10n_uy_check_vat(self, vat):
        """ Uruguayan VAT validation. TODO This need to be moved to module base_vat with name check_vat_uy when adding
        to Odoo Official """
        return stdnum.uy.rut.validate(vat)
