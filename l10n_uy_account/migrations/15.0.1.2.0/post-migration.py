from openupgradelib import openupgrade
import logging

_logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    _logger.info('Forzando actualizar grupos de impuesto (porque tienen noupdate=1)')
    openupgrade.load_data(env.cr, 'l10n_uy_account', 'migrations/15.0.1.2.0/mig_data.xml')

