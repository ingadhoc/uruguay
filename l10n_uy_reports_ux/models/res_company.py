# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Official DGI table of department codes, used by the form 3150 file (line B).
L10N_UY_DGI_DEPARTMENTS = [
    ("A", "Canelones"),
    ("B", "Maldonado"),
    ("C", "Rocha"),
    ("D", "Treinta y Tres"),
    ("E", "Cerro Largo"),
    ("F", "Rivera"),
    ("G", "Artigas"),
    ("H", "Salto"),
    ("I", "Paysandú"),
    ("J", "Río Negro"),
    ("K", "Soriano"),
    ("L", "Colonia"),
    ("M", "San José"),
    ("N", "Flores"),
    ("O", "Florida"),
    ("P", "Lavalleja"),
    ("Q", "Durazno"),
    ("R", "Tacuarembó"),
    ("V", "Montevideo"),
]


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_uy_dgi_department_code = fields.Selection(
        L10N_UY_DGI_DEPARTMENTS,
        "DGI Department",
        help="Department code reported on every line B of the form 3150 file.",
    )
    l10n_uy_dgi_locality_code = fields.Char(
        "DGI Locality Code",
        size=2,
        help="Two character locality code of the DGI table, reported on every line B of the form 3150 file."
        " For Montevideo it is AA.",
    )

    @api.constrains("l10n_uy_dgi_locality_code")
    def _check_l10n_uy_dgi_locality_code(self):
        for company in self.filtered("l10n_uy_dgi_locality_code"):
            if not re.fullmatch("[A-Z0-9]{2}", company.l10n_uy_dgi_locality_code):
                raise ValidationError(
                    _(
                        "The DGI locality code of %s has two characters, in upper case, as the AA of Montevideo.",
                        company.name,
                    )
                )
