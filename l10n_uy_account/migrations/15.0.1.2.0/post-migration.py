from openupgradelib import openupgrade
import logging

logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(
        env.cr, 'l10n_uy_account',
        'migrations/15.0.1.2.0/mig_data.xml')

    logger.info('Corregir impuestos compras UY: Ahora que los impuestos de iva y ventas deben ser diferenciados por'
                ' codigo DGI segun grupo de impuesto')
    taxes = env['account.tax'].search([('type_tax_use', '=', 'purchase')])

    # IVA Compras 22%
    taxes.filtered(lambda x: x.tax_group_id == env.ref('l10n_uy_account.tax_group_vat_22')).tax_group_id = env.ref(
        "l10n_uy_account.tax_group_2181_505")

    # IVA Compras Exento
    taxes.filtered(lambda x: x.tax_group_id == env.ref('l10n_uy_account.tax_group_vat_exempt')).tax_group_id = env.ref(
        "l10n_uy_account.tax_group_2181_504")

    # IVA Compras 10%
    taxes.filtered(lambda x: x.tax_group_id == env.ref('l10n_uy_account.tax_group_vat_10')).tax_group_id = env.ref(
        "l10n_uy_account.tax_group_2181_506")
