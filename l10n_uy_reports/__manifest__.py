# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Uruguay - Accounting Reports',
    'version': "17.0.1.0.0",
    'author': 'ADHOC SA',
    'license': 'LGPL-3',
    'category': 'Localization',
    'summary': 'Reporting for Uruguayan Localization',
    'depends': [
        'l10n_uy',
        'account_reports',
    ],
    'data': [
        'data/account_financial_report_data.xml',
        'report/account_uy_vat_line_views.xml',
        'wizards/form_report_wiz_views.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_uy_reports/static/src/components/**/*',
        ],
    },
    'auto_install': True,
    'installable': False,
}
