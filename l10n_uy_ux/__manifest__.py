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
    "version": "18.0.1.13.0",
    "depends": [
        "l10n_uy_edi",
        "certificate",
    ],
    "data": [
        "data/l10n_latam.document.type.csv",
        "data/account_journal_data.xml",
        "data/ir_cron.xml",
        "wizards/res_partner_update_from_padron_uy_wizard_view.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_view.xml",
        "views/res_partner_view.xml",
        "views/l10n_uy_addenda_views.xml",
        "views/l10n_uy_edi_document_views.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [
        "demo/res_company_demo.xml",
        "demo/res_partner_demo.xml",
    ],
    "installable": True,
    "auto_install": ["l10n_uy_edi"],
    "post_init_hook": "post_init_hook",
}
