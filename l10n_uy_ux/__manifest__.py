##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay UX',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'LGPL-3',
    'version': "17.0.1.0.0",
    'depends': [
        'l10n_uy_edi',
        'l10n_latam_check',
        # 'account_withholding', TODO activate after merged
    ],
    'data': [
        'wizards/res_partner_update_from_padron_uy_wizard_view.xml',
        'views/account_move_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'views/report_invoice.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
}
