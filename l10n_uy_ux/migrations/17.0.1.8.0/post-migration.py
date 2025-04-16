from openupgradelib import openupgrade
import logging

logger = logging.getLogger(__name__)


@openupgrade.migrate()
def migrate(env, version):
    logger.info("Forzamos llenar el campo res_model y res_id (ahora son campos requeridos y se auto agregan al crear el EDI document")
    moves_to_fix = env["l10n_uy_edi.document"].search([("res_model", "=", False), ("move_id", "!=", False)])
    for edi in moves_to_fix:
        edi.res_model = "account.move"
        edi.res_id = edi.move_id.id

    logger.info("Si aun quedan EDI documents sin res_model y sin move_id son que quedaron de errores que no se borraron: los borramos para evitar error campos requeridos")
    edi_to_delete = env["l10n_uy_edi.document"].search([("res_model", "=", False), ("move_id", "=", False), ("state", "=", "error")])
    edi_to_delete.sudo().unlink()
