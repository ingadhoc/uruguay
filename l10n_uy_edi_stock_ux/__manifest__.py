{
    "name": """Uruguay - E-Remitos""",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/EDI",
    "countries": ["uy"],
    "sequence": 12,
    "author": "ADHOC SA",
    "depends": [
        "l10n_uy_edi",
        "l10n_uy_edi_stock",
    ],
    "data": [
        "views/stock_picking_views.xml",
        "views/l10n_uy_edi_document_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "license": "LGPL-3",
}
