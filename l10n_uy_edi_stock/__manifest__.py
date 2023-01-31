{
    "name": """Uruguay - E-Remitos""",
    'version': '15.0.1.0.0',
    'category': 'Accounting/Localizations/EDI',
    'sequence': 12,
    'author': 'Adhoc',
    'description': """
    Este modulo permite a los usuarios hacer e-remitos en el sistemas que son
    reportados a la DGI
    """,
    'depends': [
        'l10n_uy_edi',
        'stock_account',
        'sale_stock',
        ],
    'data': [
        'data/l10n_latam.document.type.csv',
        'views/stock_picking_views.xml',
    ],
    'installable': False,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
