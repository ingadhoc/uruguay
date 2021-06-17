from odoo import models, _
from odoo.exceptions import UserError
from xml.etree.ElementTree import fromstring, ElementTree
import pprint
import logging
_logger = logging.getLogger(__name__)

class ResPartner(models.Model):

    _inherit = 'res.partner'

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
            'street_number': './/{DGI_Modernizacion_Consolidado}Calle_id',
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
                    [('name', '=ilike', state_name)], limit=1).id or False

                values['state_id'] = state_id
                values['street'] += ' ' + values.pop('street_number')
            else:
                raise UserError(_('No se pudo conectar a DGI para extraer los datos'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

        return values
