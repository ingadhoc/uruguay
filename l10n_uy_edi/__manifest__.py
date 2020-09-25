##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay Electronic Invoice',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'AGPL-3',
    'version': '11.0.1.1.0',
    'depends': [
        'l10n_uy',
    ],
    'data': [
        'views/res_config_settings_view.xml',
        'views/account_move_views.xml',
        'views/account_journal_view.xml',
        'wizards/res_partner_update_from_padron_wizard_view.xml',
        'views/res_partner_view.xml',
        'data/cfe_template.xml',
        'data/ir_sequence.xml',
        'demo/res_partner_demo.xml',
    ],
    'demo': [
        # TODO delete from above and uncomment here once is ready
        # 'demo/res_partner_demo.xml',
    ],
    'installable': True,
}
