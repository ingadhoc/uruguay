# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizards

import logging

from odoo.tools.safe_eval import safe_eval

logger = logging.getLogger(__name__)


def post_init_hook(env):
    logger.info(
        'Llenar campos tecnicos nuevos usados para el switch de credenciales Uruware con los datos ya existentes')
    uy_companies = env['res.company'].search([('l10n_uy_edi_ucfe_commerce_code', '!=', False)])
    env_field = {'production': 'l10n_uy_edi_ucfe_prod_env', 'testing': 'l10n_uy_edi_ucfe_test_env'}
    for company in uy_companies:
        company_field = env_field.get(company.l10n_uy_edi_ucfe_env, 'l10n_uy_edi_ucfe_test_env')
        if not safe_eval(company[company_field]):
            company[company_field] = str({
                "l10n_uy_edi_ucfe_password": company.l10n_uy_edi_ucfe_password,
                "l10n_uy_edi_ucfe_terminal_code": company.l10n_uy_edi_ucfe_terminal_code,
                "l10n_uy_edi_ucfe_commerce_code": company.l10n_uy_edi_ucfe_commerce_code,
            })
