from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):

    _inherit = 'res.partner'

    # TODO partners
    # 650 Consulta a DGI por CFE recibido

    def action_l10n_uy_is_electronic_issuer(self):
        """ Return True/False if the partner is an electronic issuer or not
        630 - Consulta si un RUT es emisor electronico """
        self.ensure_one()
        if self.main_id_category_id.l10n_uy_dgi_code == 2:
            response = self.company_id._l10n_uy_ucfe_inbox_operation('630', {'RutEmisor': self.main_id_number})
            if response.Resp.CodRta == '00':
                raise UserError(_('Es un emisor electrónico'))
            elif response.Resp.CodRta == '01':
                raise UserError(_('NO es un emisor electrónico'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

    def action_l10n_uy_get_data_from_dgi(self):
        """ 640 - Consulta a DGI por datos de RUT """
        values = {}
        if self.main_id_category_id.l10n_uy_dgi_code == 2:
            response = self.company_id._l10n_uy_ucfe_inbox_operation('640', {'RutEmisor': self.main_id_number})
            if response.Resp.CodRta == '00':
                # TODO ver detalle de los demas campos que podemos integrar en pagin 83 Manual de integración
                values = {
                    'name': response.Resp.XmlCfeFirmado.Denominacion,
                    'ref': response.Resp.XmlCfeFirmado.NombreFantasia,
                }
                # TODO delete this one once integrated
                self.message_post(body=response)
            else:
                raise UserError(_('No se pude conectar a DGI para extraer los datos'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))
        if values:
            action = self.env.ref("l10n_uy_edi.action_partner_update")
            return action.read([])[0]
