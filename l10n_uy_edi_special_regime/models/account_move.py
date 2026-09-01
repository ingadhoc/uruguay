from odoo import _, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_uy_edi_apply_special_regime(self):
        """Whether this CFE must report the special regime gross amount indicator (MntBruto = 3).

        Export CFEs keep the standard behavior: they have their own indicators (e.g. IndFact = 10) and are not
        part of the special regime treatment defined by DGI for domestic documents."""
        self.ensure_one()
        return self.company_id._l10n_uy_edi_is_special_regime() and not self._l10n_uy_edi_is_expo_cfe()

    def _l10n_uy_edi_cfe_A_iddoc(self):
        res = super()._l10n_uy_edi_cfe_A_iddoc()
        if self._l10n_uy_edi_apply_special_regime():
            # A10: DGI format validation: "Si el valor del CAE Especial es 2, 3 o 4 entonces el
            # Ind. Mnt Bruto debe ser 3". Uruware signs with special CAE = 2 when the company is
            # flagged as "Literal E o monotributo" on their side.
            res["MntBruto"] = 3
        return res

    def _get_invoice_indicator(self, line, tax_details):
        invoice_ind = super()._get_invoice_indicator(line, tax_details)
        if invoice_ind in (1, 2, 3, 4) and self.company_id._l10n_uy_edi_is_special_regime():
            # B4: per Uruware, under the special regime the indicator 16 (IVA mínimo, Monotributo
            # u otros) replaces only the VAT rate indicators (1 exempt, 2 minimum, 3 basic,
            # 4 other rate). The conceptual ones are still used: 5 (free delivery), 6/7 (non
            # billable, e.g. down payments and discount lines) and 10 (exports)
            return 16
        return invoice_ind

    def _l10n_uy_edi_special_regime_taxed_lines_error(self):
        """Error message when a special regime company bills VAT rates other than 0%, or False.

        Every CFE rejected by DGI burns a CAE number, so this is checked as early as possible."""
        self.ensure_one()
        if not (
            self.company_id.country_code == "UY"
            and self.l10n_latam_use_documents
            and self.is_invoice()
            and self.company_id._l10n_uy_edi_is_special_regime()
        ):
            return False
        lines = self.invoice_line_ids.filtered(lambda x: x.display_type not in ("line_section", "line_note"))
        if taxed := lines.tax_ids.filtered(lambda x: x.l10n_uy_tax_category == "vat" and x.amount):
            return _(
                "The company %(company)s is registered under a special DGI taxpayer regime"
                " (Literal E), so CFE lines can not include VAT taxes with a rate"
                " other than 0%% (exempt). Please fix the taxes on the invoice lines before"
                " sending (%(taxes)s)",
                company=self.company_id.name,
                taxes=", ".join(taxed.mapped("name")),
            )
        return False

    def _post(self, soft=True):
        # Block at validation time: do not let the user post a CFE we already know DGI will reject
        for move in self:
            if error := move._l10n_uy_edi_special_regime_taxed_lines_error():
                raise UserError(error)
        return super()._post(soft=soft)

    def _l10n_uy_edi_check_move(self):
        errors = super()._l10n_uy_edi_check_move()
        if error := self._l10n_uy_edi_special_regime_taxed_lines_error():
            errors.append(error)
        return errors
