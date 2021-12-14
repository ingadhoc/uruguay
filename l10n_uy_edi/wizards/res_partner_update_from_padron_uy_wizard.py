from odoo import models, api, fields, _
from ast import literal_eval
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


# TODO this code used also for 13.0 new generic module
class ResPartnerUpdate(models.TransientModel):

    # TODO rename model
    _name = 'res.partner.update.from.padron.uy.field'
    _description = 'res.partner.update.from.padron.uy.field'

    wizard_id = fields.Many2one('res.partner.update.from.padron.uy.wizard')
    field = fields.Char()
    old_value = fields.Char()
    new_value = fields.Char()


class ResPartnerUpdateFromPadronWizard(models.TransientModel):

    _name = 'res.partner.update.from.padron.uy.wizard'
    _description = 'res.partner.update.from.padron.uy.wizard'

    @api.model
    def get_partners(self):
        # TODO deberiamos buscar de otro manera estos partners
        domain = [('vat', '!=', False), ('l10n_latam_identification_type_id.l10n_uy_dgi_code', '=', '2')]
        active_ids = self._context.get('active_ids', [])
        if active_ids:
            domain.append(('id', 'in', active_ids))
        return self.env['res.partner'].search(domain)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        context = self._context
        if (context.get('active_model') == 'res.partner' and context.get('active_ids')):
            partners = self.get_partners()
            if not partners:
                raise UserError(_('No se encontró ningún partner con RUT para actualizar'))
            elif len(partners) == 1:
                res['state'] = 'selection'
                res['partner_id'] = partners[0].id
        return res

    @api.model
    def _get_domain(self):
        # TODO add our fields
        fields_names = [
            'name',
            'street',
            'street2',
            'city',
            'zip',
            'state_id',
            'country_id',
            'comment',
            'phone',
            'mobile',
            'email',
            'ref',
        ]
        return [('model', '=', 'res.partner'), ('name', 'in', fields_names)]

    @api.model
    def _get_default_title_case(self):
        parameter = self.env['ir.config_parameter'].sudo().get_param('use_title_case_on_padron_afip')
        if parameter == 'False' or parameter == '0':
            return False
        return True

    @api.model
    def get_fields(self):
        return self.env['ir.model.fields'].search(self._get_domain())

    state = fields.Selection([
        ('option', 'Option'),
        ('selection', 'Selection'),
        ('finished', 'Finished')],
        readonly=True, required=True, default='option',
    )
    field_ids = fields.One2many(
        'res.partner.update.from.padron.uy.field',
        'wizard_id',
        string='Fields',
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'partner_update_from_padron_uy_rel',
        'update_id', 'partner_id',
        string='Partners',
        default=get_partners,
    )
    partner_id = fields.Many2one('res.partner', readonly=True)
    title_case = fields.Boolean(help='Converts retreived text fields to Title Case.', default=_get_default_title_case)
    field_to_update_ids = fields.Many2many(
        'ir.model.fields',
        'res_partner_update_fields_uy',
        'update_id', 'field_id',
        string='Fields To Update',
        help='Only this fields are going to be retrived and updated',
        default=get_fields,
        domain=_get_domain,
        required=True,
    )

    @api.onchange('partner_id')
    def change_partner(self):
        self.ensure_one()
        self.field_ids.unlink()
        partner = self.partner_id
        fields_names = self.field_to_update_ids.mapped('name')
        if partner:
            partner_vals = partner.action_l10n_uy_get_data_from_dgi()
            lines = []
            # partner_vals.pop('constancia')
            for key, new_value in partner_vals.items():
                old_value = partner[key]
                if new_value == '':
                    new_value = False
                if self.title_case and key in ('name', 'city', 'street'):
                    new_value = new_value and new_value.title()
                if key in ('impuestos_padron', 'actividades_padron'):
                    old_value = old_value.ids
                elif key in ('state_id', 'country_id'):
                    old_value = old_value.id
                if new_value and key in fields_names and \
                        old_value != new_value:
                    line_vals = {
                        'wizard_id': self.id,
                        'field': key,
                        'old_value': old_value,
                        'new_value': new_value or False,
                    }
                    lines.append((0, False, line_vals))
            self.field_ids = lines

    # @mute_logger('odoo.osv.expression', 'odoo.models')
    # TODO remove this? we are not going to use it
    def _update(self):
        self.ensure_one()
        vals = {}
        for field in self.field_ids:
            if field.field in ('state_id', 'country_id'):
                vals[field.field] = literal_eval(field.new_value)
            else:
                vals[field.field] = field.new_value
        self.partner_id.write(vals)

    def automatic_process_cb(self):
        for partner in self.partner_ids:
            self.partner_id = partner.id
            self.change_partner()
            self._update()

        self.write({'state': 'finished'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def update_selection(self):
        self.ensure_one()
        if not self.field_ids:
            self.write({'state': 'finished'})
            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
        self._update()
        return self.next_cb()

    def next_cb(self):
        self.ensure_one()
        if self.partner_id:
            self.write({'partner_ids': [(3, self.partner_id.id, False)]})
        return self._next_screen()

    def _next_screen(self):
        self.ensure_one()
        self.refresh()
        values = {}
        if self.partner_ids:
            # in this case, we try to find the next record.
            partner = self.partner_ids[0]
            values.update({'partner_id': partner.id, 'state': 'selection'})
        else:
            values.update({'state': 'finished'})

        self.write(values)
        # because field is not changed, view is distroyed and reopen, on change
        # is not called an we call it manually
        self.change_partner()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def start_process_cb(self):
        """ Start the process. """
        self.ensure_one()
        return self._next_screen()
