# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError
import base64


class AccountMove(models.Model):

    _name = "account.move"
    _inherit = ['account.move', 'l10n.uy.cfe']

    l10n_uy_journal_type = fields.Selection(related='journal_id.l10n_uy_type')

    # This is required to be able to save defaults taking into account the document type selected
    l10n_latam_document_type_id = fields.Many2one(change_default=True)

    # Buttons

    def action_invoice_cancel(self):
        self.check_uy_state()
        return super().action_invoice_cancel()

    def _post(self, soft=True):
        """ After validate the invoices in odoo we send it to dgi via ucfe """
        res = super()._post(soft=soft)

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and
            x.is_invoice() and
            x.journal_id.l10n_uy_type in ['electronic', 'contingency'] and
            x.l10n_uy_ucfe_state not in x._uy_cfe_already_sent() and
            # TODO possible we are missing electronic documents here, review the
            int(x.l10n_latam_document_type_id.code) > 100)

        # Esto es para evitar que puedan crear facturas de contingencia desde el Odoo, para poder soportarlo tenemos
        # que integrar la lógica de manejar el CAE desde el lado de Odoo, enviar info de numero de serie, numero a usar
        # etc en el xml para que sea un XML valido. Una vez que este implementado esta parte se puede ir.
        if uy_invoices.filtered(lambda x: x.journal_id.l10n_uy_type == 'contingency'):
            raise UserError(_('Las facturas de Contingencia aun no están implementadas en el Odoo, para crear facturas'
                              ' de contingencia por favor generarla directamente desde al Uruware y luego cargar en el'
                              ' Odoo'))

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_invoices.filtered(lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()
            uy_invoices = uy_invoices - pre_validated_in_uruware

        if not uy_invoices:
            return res

        # Send invoices to DGI and get the return info
        for inv in uy_invoices:

            # Set the invoice rate
            if inv.company_id.currency_id == inv.currency_id:
                currency_rate = 1.0
            else:
                currency_rate = inv.currency_id._convert(
                    1.0, inv.company_id.currency_id, inv.company_id, inv.date or fields.Date.today(), round=False)
            inv.l10n_uy_currency_rate = currency_rate

            if inv._is_dummy_dgi_validation():
                inv._dummy_dgi_validation()
                continue

            # TODO KZ I think we can avoid this loop. review
            inv._l10n_uy_dgi_post()

        return res

    # TODO not working review why
    # @api.onchange('journal_id', 'state')
    # def _onchange_l10n_uy_cfe_state(self):
    #     if self.state == 'draft' and not self.l10n_uy_ucfe_state:
    #         if self.l10n_uy_journal_type not in ['electronic', 'contingency']:
    #             return 'not_apply'
    #         return 'draft_cfe'
    #     return False

    def _amount_total_company_currency(self):
        """ TODO search if Odoo already have something to do exactly the same as here """
        self.ensure_one()
        return self.amount_total if self.currency_id == self.company_currency_id else self.currency_id._convert(
            self.amount_total, self.company_id.currency_id, self.company_id, self.date or fields.Date.today(), round=False)

    # Main methods

    # Helpers

    def _uy_found_related_cfe(self):
        """ return the related/origin cfe of a given cfe """
        # next version review to merge this with l10n_ar_edi _found_related_invoice method
        self.ensure_one()
        if self.l10n_latam_document_type_id.internal_type == 'credit_note':
            return self.reversed_entry_id
        elif self.l10n_latam_document_type_id.internal_type == 'debit_note':
            return self.debit_origin_id
        else:
            return self.browse()

    def _is_uy_cfe(self):
        return bool(self.journal_id.l10n_latam_use_documents and self.company_id.country_code == "UY"
                    and self.journal_id.l10n_uy_type in ['electronic', 'contingency'])

    def check_uy_state(self):
        # TODO funcionando para facturas de clientes, ver para facturas de proveedor
        uy_sale_docs = self.filtered(lambda x: x.country_code == 'UY' and x.is_sale_document(include_receipts=True))
        super(AccountMove, uy_sale_docs).check_uy_state()

    # TODO KZ No estoy segura si esto lo necesitamos o no. capaz que no. lo agrego para mantener uniformidad, evaluar si dejarlo
    def _get_last_sequence_from_uruware(self):
        """ This method is called to return the highest number for electronic invoices, it will try to connect to Uruware
            only if it is necessary (when we are validating the invoice and need to set the document number) """
        last_number = 0 if self._is_dummy_dgi_validation() or self.l10n_latam_document_number \
            else self.journal_id._l10n_uy_get_dgi_last_invoice_number(self.l10n_latam_document_type_id)
        return "%s %08d" % (self.l10n_latam_document_type_id.doc_code_prefix, last_number)

    def _get_last_sequence(self, relaxed=False, with_prefix=None, lock=True):
        """ For uruguayan electronic invoice, if there is not sequence already then consult the last number from Uruware
        @return: string with the sequence, something like 'E-ticket 0000001"""
        res = super()._get_last_sequence(relaxed=relaxed, with_prefix=with_prefix, lock=lock)
        if self.country_code == "UY" and not res and self._is_uy_cfe() and self.l10n_latam_document_type_id:
            res = self._get_last_sequence_from_uruware()
        return res
