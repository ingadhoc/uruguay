from odoo import _, api, models
from odoo.exceptions import ValidationError


class Certificate(models.Model):
    _inherit = "certificate.certificate"

    @api.constrains("content", "pkcs12_password")
    def _l10n_uy_check_private_key(self):
        """For Uruguay we will need always the pkcs12 private key"""
        if self.company_id.country_code == "UY" and not self.pkcs12_password:
            raise ValidationError(_("Please set the Certificate Password"))
