from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _check_env(self):
        """Double-check the environment before sending any CFE to Uruware-DGI.
        To be extended in SaaS modules."""
        pass
