{
    "name": """Uruguay - E-Remitos""",
    'version': "17.0.1.0.0",
    'category': 'Accounting/Localizations/EDI',
    'countries': ['uy'],
    'sequence': 12,
    'author': 'Adhoc',
    'depends': [
        'l10n_uy_edi',
        'stock_account',
        # 'sale_stock',
        ],
    'data': [
        'data/l10n_latam.document.type.csv',
        'views/cfe_template.xml',
        'views/stock_picking_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
