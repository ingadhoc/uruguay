# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Uruguay - Accounting Reports UX",
    "version": "20.0.1.0.0",
    "author": "ADHOC SA",
    "license": "LGPL-3",
    "category": "Localization",
    "summary": "Reporting for Uruguayan Localization",
    "depends": [
        "l10n_uy_reports",
    ],
    "data": [
        "data/account_financial_report_data.xml",
        "report/account_uy_vat_line_views.xml",
        "wizards/form_report_wiz_views.xml",
        "security/ir.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_uy_reports_ux/static/src/components/**/*",
        ],
    },
    "auto_install": ["l10n_uy_reports"],
    "installable": True,
}
