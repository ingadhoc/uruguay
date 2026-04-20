{
    "name": """Uruguay - E-Remitos""",
    "version": "18.0.1.3.0",
    "category": "Accounting/Localizations/EDI",
    "countries": ["uy"],
    "sequence": 12,
    "author": "ADHOC SA",
    "depends": [
        "l10n_uy_edi",  # we needed because we extend views
        "stock_account",
        "sale_stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/l10n_latam.document.type.csv",
        "views/cfe_template.xml",
        "views/stock_picking_views.xml",
        "views/l10n_uy_edi_document_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
