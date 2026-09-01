from odoo import fields, models

# Monotributo / Monotributo MIDES should get the same treatment, but Uruware only confirmed the
# indicators for Literal E so far: add them here once confirmed
L10N_UY_EDI_SPECIAL_REGIMES = ["iva_minimo"]


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_uy_edi_taxpayer_regime = fields.Selection(
        selection=[
            ("general", "General Regime"),
            ("iva_minimo", "Minimum VAT (Literal E)"),
        ],
        string="DGI Taxpayer Regime",
        default="general",
        help="Tax regime of the company before DGI. For the Minimum VAT (Literal E) regime the CFE is built"
        " with gross amount indicator (MntBruto) = 3 and billing indicator (IndFact) = 16 on every line,"
        " as DGI requires when the CFE is signed with a special CAE.\n"
        "IMPORTANT: the option 'Literal E o monotributo' must also be enabled in the Uruware company settings"
        " ('Información Extra' section) so Uruware signs the CFE with the special CAE.",
    )

    def _l10n_uy_edi_is_special_regime(self):
        self.ensure_one()
        return self.l10n_uy_edi_taxpayer_regime in L10N_UY_EDI_SPECIAL_REGIMES
