# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import tools, models, fields, api, _


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
        sql = """CREATE or REPLACE VIEW account_uy_vat_line as (
SELECT
    am.id,
    (CASE WHEN lit.l10n_uy_dgi_code = '2' THEN rp.vat ELSE null END) as rut,
    am.name as move_name,
    rp.name as partner_name,
    am.id as move_id,
    am.move_type,
    am.date,
    am.invoice_date,
    am.partner_id,
    am.journal_id,
    am.name,
    am.l10n_latam_document_type_id as document_type_id,
    am.state,
    am.company_id,
    sum(CASE WHEN btg.name = 'VAT 22%' THEN aml.balance ELSE Null END) as base_22,
    sum(CASE WHEN ntg.name = 'VAT 22%' THEN aml.balance ELSE Null END) as vat_22,
    sum(CASE WHEN btg.name = 'VAT 10%' THEN aml.balance ELSE Null END) as base_10,
    sum(CASE WHEN ntg.name = 'VAT 10%' THEN aml.balance ELSE Null END) as vat_10,
    sum(CASE WHEN btg.name = 'VAT Exempt' THEN aml.balance ELSE Null END) as not_taxed,
    sum(CASE WHEN ntg.name not in ('VAT 22%', 'VAT 10%', 'VAT Exempt') THEN aml.balance ELSE Null END) as other_taxes,
    sum(aml.balance) as total
FROM
    account_move_line aml
LEFT JOIN
    account_move as am
    ON aml.move_id = am.id
LEFT JOIN
    -- nt = net tax
    account_tax AS nt
    ON aml.tax_line_id = nt.id
LEFT JOIN
    account_move_line_account_tax_rel AS amltr
    ON aml.id = amltr.account_move_line_id
LEFT JOIN
    -- bt = base tax
    account_tax AS bt
    ON amltr.account_tax_id = bt.id
LEFT JOIN
    account_tax_group AS btg
    ON btg.id = bt.tax_group_id
LEFT JOIN
    account_tax_group AS ntg
    ON ntg.id = nt.tax_group_id
LEFT JOIN
    res_partner AS rp
    ON rp.id = am.commercial_partner_id
LEFT JOIN
    l10n_latam_identification_type AS lit
    ON rp.l10n_latam_identification_type_id = lit.id
WHERE
    (aml.tax_line_id is not null or btg.name in ('VAT 22%', 'VAT 10%', 'VAT Exempt')) and
    am.move_type in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund')
GROUP BY
    am.id, rp.id, lit.id
ORDER BY
    am.date, am.name
       )"""
        cr.execute(sql)
