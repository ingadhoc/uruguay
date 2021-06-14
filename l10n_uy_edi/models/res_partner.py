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
        if self.l10n_latam_identification_type_id.l10n_uy_dgi_code == '2':
            response = company._l10n_uy_ucfe_inbox_operation('640', {'RutEmisor': self.vat})

            # TODO delete after finish the tests
            _logger.info("action_l10n_uy_get_data_from_dgi %s" % response)
            if response.Resp.CodRta == '00':
                # TODO ver detalle de los demas campos que podemos integrar en pagin 83 Manual de integración
                tree = ElementTree(fromstring(response.Resp.XmlCfeFirmado))

                street = tree.find('.//{DGI_Modernizacion_Consolidado}Calle_Nom').text
                street_number = tree.find('.//{DGI_Modernizacion_Consolidado}Dom_Pta_Nro').text
                city = tree.find('.//{DGI_Modernizacion_Consolidado}Loc_Nom').text
                state = tree.find('.//{DGI_Modernizacion_Consolidado}Dpto_Nom').text
                zip_code = tree.find('.//{DGI_Modernizacion_Consolidado}Dom_Pst_Cod').text
                state_id = state and self.env['res.country.state'].search([('name', '=ilike', state)], limit=1).name or False
                phone = tree.find(
                    ".//{DGI_Modernizacion_Consolidado}WS_Domicilio.WS_DomicilioItem.Contacto"
                    "[{DGI_Modernizacion_Consolidado}TipoCtt_Des='TELEFONO FIJO']/"
                    "{DGI_Modernizacion_Consolidado}DomCtt_Val").text
                email = tree.find(
                    ".//{DGI_Modernizacion_Consolidado}WS_Domicilio.WS_DomicilioItem.Contacto["
                    "{DGI_Modernizacion_Consolidado}TipoCtt_Des='CORREO ELECTRONICO']/"
                    "{DGI_Modernizacion_Consolidado}DomCtt_Val").text
                values = {
                    'name': tree.find('{DGI_Modernizacion_Consolidado}Denominacion').text,
                    'ref': tree.find('{DGI_Modernizacion_Consolidado}NombreFantasia').text,
                    'street': street + ' ' + street_number,
                    'street2':  tree.find('{DGI_Modernizacion_Consolidado}Dom_Coment').text,
                    'city': city,
                    'state_id': state_id,
                    'zip': zip_code,
                    'phone': phone,
                    'email': email,
                }
                # TODO delete this one once integrated
                self.message_post(body=response)
                self.message_post(body=values)
            else:
                _logger.info('response %s' % pprint.pformat(response))
                raise UserError(_('No se pudo conectar a DGI para extraer los datos'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))
        if values:
            action = self.env.ref("l10n_uy_edi.action_partner_update")
            return action.read([])[0]
