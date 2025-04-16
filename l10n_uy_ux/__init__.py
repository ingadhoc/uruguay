# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizards

import logging

from odoo.tools.safe_eval import safe_eval

logger = logging.getLogger(__name__)


def post_init_hook(env):
    logger.info(
        "Llenar campos tecnicos nuevos usados para el switch de credenciales Uruware con los datos ya existentes"
    )
    uy_companies = env["res.company"].search([("l10n_uy_edi_ucfe_commerce_code", "!=", False)])
    env_field = {"production": "l10n_uy_edi_ucfe_prod_env", "testing": "l10n_uy_edi_ucfe_test_env"}
    for company in uy_companies:
        company_field = env_field.get(company.l10n_uy_edi_ucfe_env, "l10n_uy_edi_ucfe_test_env")
        if not safe_eval(company[company_field]):
<<<<<<< HEAD
            company[company_field] = str(
                {
                    "l10n_uy_edi_ucfe_password": company.l10n_uy_edi_ucfe_password,
                    "l10n_uy_edi_ucfe_terminal_code": company.l10n_uy_edi_ucfe_terminal_code,
                    "l10n_uy_edi_ucfe_commerce_code": company.l10n_uy_edi_ucfe_commerce_code,
                }
            )
||||||| parent of d770ac2 (temp)
            company[company_field] = str({
                "l10n_uy_edi_ucfe_password": company.l10n_uy_edi_ucfe_password,
                "l10n_uy_edi_ucfe_terminal_code": company.l10n_uy_edi_ucfe_terminal_code,
                "l10n_uy_edi_ucfe_commerce_code": company.l10n_uy_edi_ucfe_commerce_code,
            })
=======
            company[company_field] = str({
                "l10n_uy_edi_ucfe_password": company.l10n_uy_edi_ucfe_password,
                "l10n_uy_edi_ucfe_terminal_code": company.l10n_uy_edi_ucfe_terminal_code,
                "l10n_uy_edi_ucfe_commerce_code": company.l10n_uy_edi_ucfe_commerce_code,
            })

    logger.info("Forzamos llenar nuevos campos requeridos res_model/res_id")
    moves_to_fix = env["l10n_uy_edi.document"].search([("res_model", "=", False), ("move_id", "!=", False)])
    for edi in moves_to_fix:
        edi.res_model = "account.move"
        edi.res_id = edi.move_id.id

    logger.info("Si quedan EDI docs sin res_model/move_id y tienen errores los borraromos")
    edi_to_delete = env["l10n_uy_edi.document"].search([
        ("res_model", "=", False), ("move_id", "=", False), ("state", "=", "error")])
    edi_to_delete.sudo().unlink()
>>>>>>> d770ac2 (temp)
