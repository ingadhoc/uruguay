##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
{
    'name': 'Uruguay',
    'author': 'ADHOC SA',
    'category': 'Localization',
    'license': 'AGPL-3',
    'version': '11.0.1.0.0',
    'depends': [
        'account_document',
        'account_check',
        'account_withholding',
        'l10n_ar_partner',
    ],
    'data': [
        'data/account.document.type.csv',
        'data/res.partner.id_category_data.xml',
        'data/account.group.csv',
        'data/account_tax_group_data.xml',
        'data/account_chart_template_data.xml',
        'data/account.account.template.csv',
        'data/account_tax_template_data.xml',
        'data/account_chart_template_data2.xml',
        'data/res_partner_data.xml',
        'data/account_fiscal_position_template_data.xml',
        'views/account_document_type_views.xml',
        'views/res_partner_id_category_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [
        'demo/res_company_demo.xml',
        'demo/account_chart_template_demo.xml',
        'demo/res_partner_demo.xml',
    ],
    'installable': True,
    'pre_init_hook': 'pre_init_hook',  # remove when moving to 13.0
}

# TODO not electronic invoice types
# dc_inv,,FACTURA (A CREDITO),invoice,IN ,uruguay,False
# dc_boleta_venta_contado,,BOLETA (A CONTADO),invoice,IN ,uruguay,False
# dc_cn_inv,,NOTA DE CREDITO,credit_note,CN ,uruguay,False
# dc_dn_inv,,NOTA DE DEBITO (DEVOLUCION DE CONTADO),debit_note,DB ,uruguay,False
# dc_recibo_cobranza,,RECIBO COBRANZA,invoice,IN ,uruguay,False
