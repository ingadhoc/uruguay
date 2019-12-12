##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo.api import Environment, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


def deactivate_argentinian_identification_types(cr):
    _logger.info('Deactivate Argentinian Identification types')
    env = Environment(cr, SUPERUSER_ID, {})
    env['res.partner.id_category'].search([('afip_code', '!=', 0)]).write({'active': False})


def pre_init_hook(cr):
    _logger.info('Post init hook initialized')
    deactivate_argentinian_identification_types(cr)
