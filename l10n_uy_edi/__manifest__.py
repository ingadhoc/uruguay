##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay Electronic Invoice',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'AGPL-3',
    'version': '13.0.1.0.0',
    'depends': [
        'l10n_uy',
    ],
    'external_dependencies': {
        'python': [
            'zeep',
        ],
    },
    'data': [
        'views/res_config_settings_view.xml',
        'views/account_move_views.xml',
        'wizards/res_partner_update_from_padron_uy_wizard_view.xml',
        'views/res_partner_view.xml',
        'data/cfe_template.xml',
        'data/ir_sequence.xml',
        'data/ir_actions_server.xml',
        'data/ir_cron.xml',
        'data/account_incoterms_data.xml',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
        'demo/res_company_demo.xml',
        'demo/account_journal_demo.xml',
    ],
    'installable': True,
}