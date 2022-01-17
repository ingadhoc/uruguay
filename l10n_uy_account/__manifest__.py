##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay - Accounting',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'LGPL-3',
    'version': '13.0.1.5.0',
    'depends': [
        'l10n_latam_invoice_document',
        'l10n_latam_base',

        # TODO move it to l10n_uy_ux once we have it?
        'account_check',
        'account_withholding',
    ],
    'data': [
        'data/l10n_latam.document.type.csv',
        'data/l10n_latam_identification_type_data.xml',
        'data/account.group.csv',
        'data/account_tax_group_data.xml',
        'data/account_chart_template_data.xml',
        'data/account.account.template.csv',
        'data/account_tax_template_data.xml',
        'data/res_partner_data.xml',
        'data/account_fiscal_position_template_data.xml',
        'views/l10n_latam_document_type_views.xml',
        'views/account_move_views.xml',
        'views/account_journal_view.xml',
        'views/res_company_view.xml',
        'data/account_chart_template_data2.xml',
        'data/res.country.state.csv',
        'data/res_currency_data.xml',
        'data/res_currency_rate_data.xml',
    ],
    'demo': [
        'demo/res_company_demo.xml',
        'demo/account_chart_template_demo.xml',
        'demo/res_partner_demo.xml',
        # restore
        'demo/res_users_demo.xml',
    ],
    'installable': False,
}
