from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_uy_payment_type = fields.Selection([('cash', 'Cash'), ('credit', 'Credit')], 'CFE Payment Type', default='cash')
    # TODO this can be removed and integrated with the payment methods we already have in odoo

    l10n_uy_currency_rate = fields.Float(copy=False, digits=(16, 4), string="Currency Rate (UY)")
    # TODO integrate with l10n_ar_currency_rate in next versions
    # solo mostrar en estado draft?

    @api.constrains('move_type', 'journal_id')
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

    def get_uy_sales_vat_tax_groups(self):
        return self.env.ref('l10n_uy_account.tax_group_vat_22') + self.env.ref('l10n_uy_account.tax_group_vat_10') \
            + self.env.ref('l10n_uy_account.tax_group_vat_exempt')

    def _check_uruguayan_invoices(self):
        uy_invs = self.filtered(lambda x: (x.company_id.country_id.code == 'UY' and x.l10n_latam_use_documents))
        if not uy_invs:
            return True
        uy_invs.mapped('partner_id').check_vat()

        uruguayan_vat_taxes = self.get_uy_sales_vat_tax_groups()

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

    def _get_l10n_latam_documents_domain(self):
        self.ensure_one()
        domain = super()._get_l10n_latam_documents_domain()
        if self.journal_id.company_id.country_id.code == 'UY':
            codes = self.journal_id._l10n_uy_get_journal_codes()
            if codes:
                domain.extend([('code', 'in', codes), ('active', '=', True)])
        return domain

    def unlink(self):
        """ When using documents on vendor bills the document_number is set manually by the number given from the vendor
        so the odoo sequence is not used. In this case we allow to delete vendor bills with document_number/name """
        self.filtered(lambda x: x.move_type in x.get_purchase_types() and x.state in ('draft', 'cancel') and
                      x.l10n_latam_use_documents).write({'name': '/'})
        return super().unlink()

    def _post(self, soft=True):
        uy_invoices = self.filtered(lambda x: x.company_id.country_id.code == 'UY' and x.l10n_latam_use_documents)
        # We make validations here and not with a constraint because we want validation before sending electronic
        # data on l10n_uy_edi
        uy_invoices._check_uruguayan_invoices()
        res = super()._post(soft=soft)
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
    #             final_consumer=self.env.ref('l10n_uy_account.it_dni') + self.env.ref('l10n_uy_account.it_ci') +
    #             self.env.ref('l10n_uy_account.it_pass') + self.env.ref('l10n_uy_account.it_other') + self.env.ref('l10n_uy_account.it_nie'),
    #             company=self.env.ref('l10n_uy_account.it_rut') + self.env.ref('l10n_uy_account.it_nife'))
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

    @api.depends('name')
    def _compute_l10n_latam_document_number(self):
        """En el metodo original en latam suponemos que el codigo del tipo de documento no tiene espacios.
        Y por ello conseguimos el numero haciendo el split al coseguir el primer espacio en blanco.

        En este caso los nombres de docs uruguayos tienen espacios. por eso necesitamos tomar otro criterio.
        Este metodo lo que hace es llamar el original y posterior corregir los documentos uruguayos para solo tomar
        realmente la ultima parte del name seria el numero en si.

        Sin este cambio, si el name es "ND e-Ticket 00000001" coloca el "e-Ticket 00000001" como numero de doc
        Con este cambio, si el name es "ND e-Ticket 00000001" coloca el "00000001" como numero de doc"""
        super(AccountMove, self)._compute_l10n_latam_document_number()
        uy_recs_with_name = self.filtered(lambda x: x.country_code == 'UY' and x.name != '/')
        for rec in uy_recs_with_name:
            name = rec.l10n_latam_document_number
            doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
            if doc_code_prefix and name:
                name = name.split(" ")[-1]
            rec.l10n_latam_document_number = name

    # Los metodos siguientes son en realidad copia de lo que teemos e l10n_ar y los necesitamos para que pueda funcionar
    # el correcto nombramiento de los facturas/nc/nd usando el prefijo apropiado segun el tipo de documento y su
    # respectivo siguiente numero a usar ahora que no existen las secuencias

    def _get_starting_sequence(self):
        """ If use documents then will create a new starting sequence using the document type code prefix and the
        journal document number with a 8 padding number """
        if self.journal_id.l10n_latam_use_documents and self.country_code == "UY" and self.l10n_latam_document_type_id:
            return self._uy_get_formatted_sequence()
        return super()._get_starting_sequence()

    def _uy_get_formatted_sequence(self, number=0):
        return "%s %08d" % (self.l10n_latam_document_type_id.doc_code_prefix, number)

    def _get_last_sequence(self, relaxed=False, with_prefix=None, lock=True):
        """ If use share sequences we need to recompute the sequence to add the proper document code prefix """
        res = super()._get_last_sequence(relaxed=relaxed, with_prefix=with_prefix, lock=lock)
        if self.country_code == 'UY' and self.l10n_latam_use_documents and res \
           and self.l10n_latam_document_type_id.doc_code_prefix not in res:
            res = self._uy_get_formatted_sequence(number=res.split()[-1])
        return res

    def _get_last_sequence_domain(self, relaxed=False):
        where_string, param = super(AccountMove, self)._get_last_sequence_domain(relaxed)
        if self.country_code == "UY" and self.l10n_latam_use_documents:
            where_string += " AND l10n_latam_document_type_id = %(l10n_latam_document_type_id)s"
            param['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id or 0
        return where_string, param
