from odoo import api, models, fields


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_uy_edi_send_print = fields.Boolean(compute="_compute_l10n_uy_edi_send_print", readonly=False, store=True)

    @api.depends("type", "l10n_uy_edi_type")
    def _compute_l10n_uy_edi_send_print(self):
        """
        Set Auto pop up Send and Print default value to True for electronic sales journals
        """
        for journal in self:
            if journal.country_code == 'UY' and journal.type == 'sale' and journal.l10n_uy_edi_type == "electronic":
                journal.l10n_uy_edi_send_print = True
            else:
                journal.l10n_uy_edi_send_print = False
