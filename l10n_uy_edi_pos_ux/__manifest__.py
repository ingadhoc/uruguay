{
    "name": "Uruguay - E-Invoicing POS UX",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "countries": ["uy"],
    "author": "ADHOC SA",
    "depends": [
        "l10n_uy_ux",
        "point_of_sale",
    ],
    "data": [
        "views/account_move_views.xml",
        "views/account_portal_templates.xml",
        "views/pos_order_views.xml",
    ],
    "demo": [
        "demo/pos_config_demo.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_uy_edi_pos_ux/static/src/**/*",
        ],
        "web.assets_tests": [
            "l10n_uy_edi_pos_ux/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "auto_install": True,
    "application": False,
    "license": "LGPL-3",
}
