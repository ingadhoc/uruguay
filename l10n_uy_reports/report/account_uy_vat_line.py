# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools


class AccountUyVatLine(models.Model):
    """ Base model for new Uruguayan VAT reports. The idea is that this lines have all the necessary data and which any
    changes in odoo, this ones will be taken for this cube and then no changes will be nedeed in the reports that use
    this lines. A line is created for each accountring entry that is affected by VAT tax.

    Basically which it does is covert the accounting entries into columns depending of the information of the taxes and
    add some other fields """

    _name = "account.uy.vat.line"
    _description = "VAT line for Analysis in Uruguayan Localization"
    _auto = False
    _order = 'invoice_date asc, move_name asc, id asc'

    document_type_id = fields.Many2one('l10n_latam.document.type', 'Document Type', readonly=True)
    date = fields.Date(readonly=True)
    invoice_date = fields.Date(readonly=True)
    rut = fields.Char(readonly=True)
    partner_name = fields.Char(readonly=True)
    move_name = fields.Char(readonly=True)
    move_type = fields.Selection(selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
        ], readonly=True)
    base_22 = fields.Monetary(readonly=True, string='Base 22%', currency_field='company_currency_id')
    vat_22 = fields.Monetary(readonly=True, string='VAT 22%', currency_field='company_currency_id')
    base_10 = fields.Monetary(readonly=True, string='Base 10%', currency_field='company_currency_id')
    vat_10 = fields.Monetary(readonly=True, string='VAT 10%', currency_field='company_currency_id')
    not_taxed = fields.Monetary(
        readonly=True, string='Not taxed/ex', help='Not Taxed / Exempt. All lines that have does not have VAT', currency_field='company_currency_id')
    other_taxes = fields.Monetary(
        readonly=True, string='Other Taxes', help='All the taxes tat ar not VAT taxes or iibb perceptions and that'
        ' are realted to documents that have VAT', currency_field='company_currency_id')
    total = fields.Monetary(readonly=True, currency_field='company_currency_id')
    state = fields.Selection([('draft', 'Unposted'), ('posted', 'Posted')], 'Status', readonly=True)
    journal_id = fields.Many2one('account.journal', 'Journal', readonly=True, auto_join=True)
    partner_id = fields.Many2one('res.partner', 'Partner', readonly=True, auto_join=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, auto_join=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    move_id = fields.Many2one('account.move', string='Entry', auto_join=True)

    def open_journal_entry(self):
        self.ensure_one()
        return self.move_id.get_formview_action()

    def init(self):
        cr = self._cr
        tools.drop_view_if_exists(cr, self._table)
        # we use tax_ids for base amount instead of tax_base_amount for two reasons:
        # * zero taxes do not create any aml line so we can't get base for them with tax_base_amount
        # * we use same method as in odoo tax report to avoid any possible discrepancy with the computed tax_base_amount
        query, params = self._uy_vat_line_build_query()
        sql = f"""CREATE or REPLACE VIEW account_uy_vat_line as ({query})"""
        cr.execute(sql, params)

    @api.model
    def _uy_vat_line_build_query(self, tables='account_move_line', where_clause='', where_params=None,
                                 column_group_key='', tax_types=('sale', 'purchase')):
        """Returns the SQL Select query fetching account_move_lines info in order to build the pivot view for the VAT summary.
        This method is also meant to be used outside this model, which is the reason why it gives the opportunity to
        provide a few parameters, for which the defaults are used in this model.

        The query is used to build the VAT book report"""
        if where_params is None:
            where_params = []

        query = f"""
                SELECT
                    %s AS column_group_key,
                    account_move.id,
                    (CASE WHEN lit.l10n_uy_dgi_code = '2' THEN rp.vat ELSE NULL END) AS rut,
                    account_move.name as move_name,
                    rp.name AS partner_name,
                    account_move.id AS move_id,
                    COALESCE(nt.type_tax_use, bt.type_tax_use) AS tax_type,
                    account_move.move_type,
                    account_move.date,
                    account_move.invoice_date,
                    account_move.partner_id,
                    account_move.journal_id,
                    account_move.l10n_latam_document_type_id as document_type_id,
                    account_move.state,
                    account_move.company_id,
                    SUM(CASE WHEN btg.l10n_uy_vat_code = 'vat_22' THEN account_move_line.balance ELSE 0 END) AS base_22,
                    SUM(CASE WHEN ntg.l10n_uy_vat_code = 'vat_22' THEN account_move_line.balance ELSE 0 END) AS vat_22,
                    SUM(CASE WHEN btg.l10n_uy_vat_code = 'vat_10' THEN account_move_line.balance ELSE 0 END) AS base_10,
                    SUM(CASE WHEN ntg.l10n_uy_vat_code = 'vat_10' THEN account_move_line.balance ELSE 0 END) AS vat_10,
                    SUM(CASE WHEN btg.l10n_uy_vat_code = 'vat_exempt' THEN account_move_line.balance ELSE 0 END) AS not_taxed,
                    SUM(CASE WHEN btg.l10n_uy_vat_code in ('vat_22', 'vat_10') THEN account_move_line.balance ELSE 0 END) AS taxed,
                    SUM(CASE WHEN ntg.l10n_uy_vat_code not in ('vat_22', 'vat_10', 'vat_exempt') THEN account_move_line.balance ELSE 0 END) AS other_taxes,
                    SUM(account_move_line.balance) AS total
                FROM
                    {tables}
                    JOIN
                        account_move ON account_move_line.move_id = account_move.id
                    LEFT JOIN
                        -- nt = net tax
                        account_tax AS nt ON account_move_line.tax_line_id = nt.id
                    LEFT JOIN
                        account_move_line_account_tax_rel AS amltr ON account_move_line.id = amltr.account_move_line_id
                    LEFT JOIN
                        -- bt = base tax
                        account_tax AS bt ON amltr.account_tax_id = bt.id
                    LEFT JOIN
                        account_tax_group AS btg ON btg.id = bt.tax_group_id
                    LEFT JOIN
                        account_tax_group AS ntg ON ntg.id = nt.tax_group_id
                    LEFT JOIN
                        res_partner AS rp ON rp.id = account_move.commercial_partner_id
                    LEFT JOIN
                        l10n_latam_identification_type AS lit ON rp.l10n_latam_identification_type_id = lit.id
                    WHERE
                        (account_move_line.tax_line_id is not NULL OR btg.l10n_uy_vat_code IN ('vat_22', 'vat_10', 'vat_exempt')) AND
                        account_move.move_type IN ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
                        AND (nt.type_tax_use in %s OR bt.type_tax_use in %s)
                    {where_clause}
                GROUP BY
                    account_move.id, rp.id, lit.id, tax_type
                ORDER BY
                    account_move.date, account_move.name"""

        return query, [column_group_key, tax_types, tax_types, *where_params]
