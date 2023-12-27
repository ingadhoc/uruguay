##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay Electronic Invoice',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'LGPL-3',
<<<<<<< HEAD
    'version': "16.0.1.7.0",
||||||| parent of 7797dc8 (temp)
    'version': '15.0.1.8.0',
=======
    'version': '15.0.1.9.0',
>>>>>>> 7797dc8 (temp)
    'depends': [
        'l10n_uy_account',
        'account_debit_note',
    ],
    'external_dependencies': {
        'python': [
            'zeep',
        ],
    },
    'data': [
        'views/res_config_settings_view.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'wizards/res_partner_update_from_padron_uy_wizard_view.xml',
        'views/res_partner_view.xml',
        'views/product_view.xml',
        'data/cfe_template.xml',
        'data/ir_sequence.xml',
        'data/ir_actions_server.xml',
        'data/ir_actions_report_data.xml',
        'data/ir_cron.xml',
        'data/account_incoterms_data.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/res_company_demo.xml',
        'demo/account_journal_demo.xml',
    ],
    'installable': True,
}
