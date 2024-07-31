import logging
import pprint
import stdnum
from stdnum.exceptions import InvalidLength, InvalidChecksum, InvalidFormat
from xml.etree.ElementTree import fromstring, ElementTree

from odoo import _, api, fields, models

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):

    _inherit = 'res.partner'

    fiscal_countries = fields.Many2many('res.country', compute="compute_fiscal_countries")

    def action_l10n_uy_is_electronic_issuer(self):
        """ Return True/False if the partner is an electronic issuer or not
        630 - Consulta si un RUT es emisor electronico """
        self.ensure_one()
        company = self.company_id or self.env.company
        # TODO KZ need to ensure that use the proper company
        edi_doc = self.env['l10n_uy_edi.document']
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2':
            result = edi_doc._ucfe_inbox('630', {'RutEmisor': self.vat})

            cod_rta = False
            response = result.get('response')
            if response is not None:
                cod_rta = response.findtext(".//{*}CodRta")

            if cod_rta == '00':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'info',
                        'message': _('Es un emisor electrónico'),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
            elif cod_rta == '01':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'danger',
                        'message': _('NO es un emisor electrónico'),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

    def action_l10n_uy_get_data_from_dgi(self):
        """ 640 - Consulta a DGI por datos de RUT """
        self.ensure_one()
        company = self.company_id or self.env.company
        values = {}

        data_mapping = {
            'street': './/{DGI_Modernizacion_Consolidado}Calle_Nom',

            'city': './/{DGI_Modernizacion_Consolidado}Loc_Nom',
            'zip': './/{DGI_Modernizacion_Consolidado}Dom_Pst_Cod',
            'phone':
                ".//{DGI_Modernizacion_Consolidado}WS_Domicilio.WS_DomicilioItem.Contacto"
                "[{DGI_Modernizacion_Consolidado}TipoCtt_Des='TELEFONO FIJO']/"
                "{DGI_Modernizacion_Consolidado}DomCtt_Val",
            'mobile':
                ".//{DGI_Modernizacion_Consolidado}WS_Domicilio.WS_DomicilioItem.Contacto"
                "[{DGI_Modernizacion_Consolidado}TipoCtt_Des='TELEFONO MOVIL']/"
                "{DGI_Modernizacion_Consolidado}DomCtt_Val",
            'email':
                ".//{DGI_Modernizacion_Consolidado}WS_Domicilio.WS_DomicilioItem.Contacto["
                "{DGI_Modernizacion_Consolidado}TipoCtt_Des='CORREO ELECTRONICO']/"
                "{DGI_Modernizacion_Consolidado}DomCtt_Val",

            'name': './/{DGI_Modernizacion_Consolidado}Denominacion',
            'ref': './/{DGI_Modernizacion_Consolidado}NombreFantasia',
            'street2':  './/{DGI_Modernizacion_Consolidado}Dom_Coment',

            # TODO remove
            'street_number': './/{DGI_Modernizacion_Consolidado}Dom_Pta_Nro',
            'state': './/{DGI_Modernizacion_Consolidado}Dpto_Nom',
        }

        # If partner has RUC
        edi_doc = self.env['l10n_uy_edi.document']
        # TODO KZ need to ensure that use the proper company
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2':
            response = edi_doc._ucfe_inbox('640', {'RutEmisor': self.vat})
            # TODO delete after finish the tests
            _logger.info('response %s' % pprint.pformat(response))

            if response.Resp.CodRta == '00':
                # TODO ver detalle de los demas campos que podemos integrar en pagin 83 Manual de integración
                tree = ElementTree(fromstring(response.Resp.XmlCfeFirmado))

                values = {}
                for odoo_field, mapping_value in data_mapping.items():
                    val = tree.findtext(mapping_value)
                    if val:
                        values.update({odoo_field: val})

                state_name = values.pop('state')
                state_id = state_name and self.env['res.country.state'].search(
                    [('name', '=ilike', state_name)], limit=1)

                values['state_id'] = state_id.id or False
                if state_id:
                    values['country_id'] = state_id.country_id.id
                if 'street' in values:
                    values['street'] += ' ' + values.get('street_number')
                # Este campo no existe en odoo base, asi que tenemos que
                # removerlo siempre del values
                values.pop('street_number')
            else:
                raise UserError(_('No se pudo conectar a DGI para extraer los datos'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

        return values

    # TODO KZ From here to to bottom is a patch, we think this should be fixed directly
    # in l10n_latam_base module, if approved, then we need to move it to l10n_latam_base.
    # meanwhile we leave here as a patch
    def _get_countries(self):
        self.ensure_one()
        countries = self.env['res.country'].search([('code', 'in', self.fiscal_country_codes.split(','))])
        if not countries:
            countries = self.country_id
        return countries

    @api.onchange('country_id', 'company_id')
    def _onchange_country(self):
        """ Take into account the fiscal countries to filter the identification types,
        if not define ones, then use the partner country
        """
        # TODO Ahora que vamos a re-usar los tipos genericos toca ver de revisar esto, porque tenemos que tomar en cuenta los que no tienen pais,
        super()._onchange_country()
        countries = self._get_countries()
        if countries:
            identification_type = self.l10n_latam_identification_type_id
            if not identification_type or (identification_type.country_id not in countries):
                self.l10n_latam_identification_type_id = self.env['l10n_latam.identification.type'].search(
                    [('country_id', 'in', countries.ids), ('is_vat', '=', True)], limit=1) or self.env.ref(
                        'l10n_latam_base.it_vat', raise_if_not_found=False)

    @api.onchange('company_id')
    def compute_fiscal_countries(self):
        """ Only used for """
        for rec in self:
            rec.fiscal_countries = rec._get_countries()

    @api.onchange('vat',  'l10n_latam_identification_type_id')
    def _l10n_uy_edi_onchange_document_number(self):
        """ Show warning to the user when editing the vat number """
        msg = self._l10n_uy_edi_identification_validation()
        if msg:
            return {'warning': {'title': "Warning", 'message': msg, 'type': 'notification'}}

    """ TODO KZ despues que se mezcle el pr de check vat, agregar esto
    def check_vat(self, vat):
        # NOTE by the moment we include the RUT (VAT UY) validation also here because we extend the messages errors to be
        # more friendly to the user. In a future when Odoo improve the base_vat message errors  we can change
        # this method and use the base_vat.check_vat_uy method instead.
        valid = super().check_vat_uy()
        if not valid and vat:
            self._l10n_uy_edi_check_ruc_rut(vat)
        return valid

    @api.model
    def _l10n_uy_edi_check_ruc_rut(self, vat):
        # Check if the VAT is valid.
        # Return: False if valid vat number, a msg containing the error if not
        # NOTE: This method is only to add more info to the error
        # TODO this will not work we need to improved to properly show message error
        msg = False
        try:
            stdnum.util.get_cc_module('uy', 'rut').validate(vat)
        except ImportError:
            _logger.warning('Urugayan RUT/RUC can not be validated (missing stnum lib)')
        except InvalidChecksum:
            msg = _('The validation digit is not valid')
        except InvalidLength:
            msg = _('Invalid length')
        except InvalidFormat:
            msg = _('Only numbers allowed')

        return msg
    """
