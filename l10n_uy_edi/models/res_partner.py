from odoo import api, models,fields,  _
from odoo.exceptions import UserError
from xml.etree.ElementTree import fromstring, ElementTree
import pprint
import logging
_logger = logging.getLogger(__name__)


class ResPartner(models.Model):

    _inherit = 'res.partner'

    l10n_uy_additional_info = fields.Text(
        "Info. adicional del receptor",
        help='Información adicional del receptor')

    # TODO partners
    # 650 Consulta a DGI por CFE recibido

    def action_l10n_uy_is_electronic_issuer(self):
        """ Return True/False if the partner is an electronic issuer or not
        630 - Consulta si un RUT es emisor electronico """
        self.ensure_one()
        company = self.company_id or self.env.company
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2':
            response = company._l10n_uy_ucfe_inbox_operation('630', {'RutEmisor': self.vat})
            if response.Resp.CodRta == '00':
                raise UserError(_('Es un emisor electrónico'))
            elif response.Resp.CodRta == '01':
                raise UserError(_('NO es un emisor electrónico'))
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
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2':
            response = company._l10n_uy_ucfe_inbox_operation('640', {'RutEmisor': self.vat})
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
                raise UserError(_('No puede obtener datos de DGi. Puede ser que el servicio del Padron este caido o haya algun problema'
                                  ' particular con el RUT a consultar. Por favor verifique primero que el RUT que esta intentando '
                                  'consultar es un emisor electronico (esta consulta al padron solo funciona para emisores electronicos).'
                                  '\n\nSi el contacto es emisor electronico y sigue teniendo problemas por favor avisar via ticket a'
                                  ' ADHOC para revisar el caso particular'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

        return values

    # TODO this need to be fixed directly in l10n_latam_base module, menawhile we leave here the patch
    @api.onchange('country_id')
    def _onchange_country(self):
        """ New logic will take the company country to show the identification type:
        * the country of the invoice
        * if not the company of the environment.
        * if not then the country of the partner
        """
        super()._onchange_country()
        country = (self.company_id and self.company_id.country_id) or self.env.company.country_id or self.country_id
        identification_type = self.l10n_latam_identification_type_id
        if not identification_type or (identification_type.country_id != country):
            self.l10n_latam_identification_type_id = self.env['l10n_latam.identification.type'].search(
                [('country_id', '=', country.id), ('is_vat', '=', True)], limit=1) or self.env.ref(
                    'l10n_latam_base.it_vat', raise_if_not_found=False)
        return {'domain': {'l10n_latam_identification_type_id': [('country_id', '=', country.id)]}}
