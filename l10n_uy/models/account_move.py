from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_uy_payment_type = fields.Selection([('cash', 'Cash'), ('credit', 'Credit')], 'Payment Type', default='cash')
    # TODO this can be removed and integrated with the payment methods we already have in odoo

    l10n_uy_currency_rate = fields.Float(copy=False, digits=(16, 4), string="Currency Rate")
    # TODO integrate with l10n_ar_currency_rate in next versions

    @api.constrains('type', 'journal_id')
    def _l10n_uy_check_moves_use_documents(self):
        """ Do not let to create not invoices entries in journals that use documents """
        # TODO simil to _check_moves_use_documents. integrate somehow
        not_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and x.journal_id.type in ['sale', 'purchase'] and
            x.l10n_latam_use_documents and not x.is_invoice())
        if not_invoices:
            raise ValidationError(_(
                "The selected Journal can't be used in this transaction, please select one that doesn't use documents"
                " as these are just for Invoices."))

    def _check_uruguayan_invoices(self):
        uy_invs = self.filtered(lambda x: (x.company_id.country_id.code == 'UY' and x.l10n_latam_use_documents))
        if not uy_invs:
            return True

        uruguayan_vat_taxes = self.env.ref('l10n_uy.tax_group_vat_22') + self.env.ref('l10n_uy.tax_group_vat_10') \
            + self.env.ref('l10n_uy.tax_group_vat_exempt')

        # Check that we do not send any tax in exportation invoices
        expo_cfes = uy_invs.filtered(
            lambda x: int(x.l10n_latam_document_type_id.code) in [121, 122, 123])
        for inv_line in expo_cfes.mapped('invoice_line_ids'):
            vat_taxes = inv_line.tax_line_id.filtered(lambda x: x.tax_group_id in uruguayan_vat_taxes)
            if len(vat_taxes) != 0:
                raise ValidationError(_(
                    'Should not be any VAT tax in the exportation cfe line "%s" (Id Invoice: %s)' % (
                        inv_line.product_id.name, inv_line.move_id.id)))

        # We check that there is one and only one vat tax per line
        for line in (uy_invs - expo_cfes).mapped('invoice_line_ids').filtered(
                lambda x: x.display_type not in ('line_section', 'line_note')):
            vat_taxes = line.tax_ids.filtered(lambda x: x.tax_group_id in uruguayan_vat_taxes)
            if len(vat_taxes) != 1:
                raise ValidationError(_(
                    'Should be one and only one VAT tax per line. Verify lines with product "%s" (Id Invoice: %s)' % (
                        line.product_id.name, line.move_id.id)))

    def _get_document_type_sequence(self):
        """ Return the match sequences for the given journal and invoice """
        self.ensure_one()
        if self.journal_id.l10n_latam_use_documents and self.l10n_latam_country_code == 'UY':
            if self.journal_id.l10n_uy_share_sequences:
                return self.journal_id.l10n_uy_sequence_ids
            res = self.journal_id.l10n_uy_sequence_ids.filtered(
                lambda x: x.l10n_latam_document_type_id == self.l10n_latam_document_type_id)
            return res
        return super()._get_document_type_sequence()

    def _get_l10n_latam_documents_domain(self):
        self.ensure_one()
        domain = super()._get_l10n_latam_documents_domain()
        if self.journal_id.company_id.country_id.code == 'UY':
            codes = self.journal_id._l10n_uy_get_journal_codes()
            if codes:
                domain.extend([('code', 'in', codes), ('active', '=', True)])
        print(" --- l10n_uy domain %s" % domain)
        return domain

    def unlink(self):
        """ When using documents on vendor bills the document_number is set manually by the number given from the vendor
        so the odoo sequence is not used. In this case we allow to delete vendor bills with document_number/name """
        self.filtered(lambda x: x.type in x.get_purchase_types() and x.state in ('draft', 'cancel') and
                      x.l10n_latam_use_documents).write({'name': '/'})
        return super().unlink()

    def post(self):
        uy_invoices = self.filtered(lambda x: x.company_id.country_id.code == 'UY' and x.l10n_latam_use_documents)
        # We make validations here and not with a constraint because we want validation before sending electronic
        # data on l10n_uy_edi
        uy_invoices._check_uruguayan_invoices()
        res = super().post()
        return res

    # TODO review if we actually want to add the logic of filter de documents per type of partner commercial or final
    # consumer, I think will be use for pre printed but should not be applied to electronic/contingencia
    # @api.model
    # def _get_available_journal_document_types(self, journal, invoice_type, partner):
    #     """ This function filter the journal documents types taking into account the partner identification type """
    #     res = super()._get_available_journal_document_types(journal, invoice_type, partner)
    #     if journal.localization == 'uruguay' and partner:
    #         available_types = self.env['account.journal.document.type']
    #         commercial_partner = partner.commercial_partner_id
    #         partner_type = dict(
    #             final_consumer=self.env.ref('l10n_uy.it_dni') + self.env.ref('l10n_uy.it_ci') +
    #             self.env.ref('l10n_uy.it_pass') + self.env.ref('l10n_uy.it_other') + self.env.ref('l10n_uy.it_nie'),
    #             company=self.env.ref('l10n_uy.it_rut') + self.env.ref('l10n_uy.it_nife'))
    #         # TODO we can improve this if we separete ticket and invoice tye documents, but we have a problem, need to
    #         # add a new seperation for dn and cn
    #         if commercial_partner.l10n_latam_identification_type_id in partner_type['final_consumer']:
    #             # e-tickets docs
    #             available_types = [000, 101, 102, 103, 131, 132, 133, 201, 202, 203, 231, 232, 233]
    #         elif commercial_partner.l10n_latam_identification_type_id in partner_type['company']:
    #             # e-invoices docs
    #             available_types = [000, 111, 112, 113, 121, 122, 123, 141, 142, 143, 201, 211, 212, 213, 221, 222,
    #                                223, 241, 242, 243]
    #         else:
    #             res['available_journal_document_types'] = False
    #             res['journal_document_type'] = False
    #         if available_types:
    #             res['available_journal_document_types'] = res['available_journal_document_types'].filtered(
    #                 lambda x: int(x.l10n_latam_document_type_id.code) in available_types)
    #             res['journal_document_type'] = res['available_journal_document_types'] and \
    #                 res['available_journal_document_types'][0]
    #     return res
