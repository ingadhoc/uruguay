##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    "name": "Uruguay UX",
    "author": "ADHOC SA",
    "category": "Localization",
    "countries": ["uy"],
    "license": "LGPL-3",
    "version": "17.0.1.0.0",
    "depends": [
        "l10n_uy_edi",
    ],
    "data": [
        "wizards/res_partner_update_from_padron_uy_wizard_view.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_view.xml",
        "views/res_partner_view.xml",
        "views/cfe_template.xml",
        "views/l10n_uy_addenda_views.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [
        "demo/res_company_demo.xml",
    ],
    "installable": True,
}
