# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models

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
