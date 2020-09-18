##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay Electronic Invoice',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'AGPL-3',
    'version': '11.0.1.0.0',
    'depends': [
        'l10n_uy',
    ],
    'data': [
        'views/res_config_settings_view.xml',
        'data/cfe_template.xml',
        'data/CFEType.xsd',
        # 'data/dgi_eTck.xml',
    ],
    'demo': [
        'demo/res_company_demo.xml',
    ],
    'installable': True,
}
