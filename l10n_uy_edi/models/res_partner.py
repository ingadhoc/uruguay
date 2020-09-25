from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):

    _inherit = 'res.partner'

    # TODO partners
    # 650 Consulta a DGI por CFE recibido

    def _l10n_uy_is_electronic_issuer(self):
        """ Return True/False if the partner is an electronic issuer or not """
        self.ensure_one()
        if self.main_id_category_id.l10n_uy_dgi_code == 2:
            # 630 - Consulta si un RUT es emisor electronico
            response = self.company_id._l10n_uy_ucfe_inbox_operation('630', {'RutEmisor': self.main_id_number})
            return response.Resp.CodRta == '00'
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))

    def _l10n_uy_get_data_from_dgi(self):
        if self.main_id_category_id.l10n_uy_dgi_code == 2:
            # 640 Consulta a DGI por datos de RUT
            response = self.company_id._l10n_uy_ucfe_inbox_operation('640', {'RutEmisor': self.main_id_number})
            if response.Resp.CodRta == '00':
                pass
                # TODO response.Resp.XmlCfeFirmado
                # • Rut
                # • Denominación
                # • Nombre fantasía
                # • Tipo de entidad
                # • Descripción tipo de entidad
                # • Estado de actividad empresarial cuyos valores posibles son:
                #   o AA, activo
                #   o AF, activo futuro
                #   o CC, cancelado
                #   o CH, cancelado hoy
                #   o NT, nunca tuvo
                # • Fecha inicio actividad empresarial
                # • Local principal
                # • Domicilio del local principal
                # • TipoDom_Id (tipo de domicilio)
                # • TipoDom_Des
                # • CalOcup_id (calidad en que ocupa el domicilio)
                # • Calocup_Des
                # • TerCod_Id (código territorial)
                # • Tercod_Des
                # • Calle_id
                # • Calle_Nom
                # • Dom_Pta_Nro
                # • Dom_Bis_Flg
                # • Dom_Ap_Nro
                # • Loc_Id (localidad)
                # • Loc_Nom
                # • Dpto_Id (departamento)
                # • Dpto_Nom
                # • Dom_Pst_Cod
                # • Dom_Coment
                # • Dom_Err_Cod
                # • Contactos (colección de teléfonos, correos electrónicos)
                # • Complementos (colección de datos de ubicación)
                # • Giros (colección de actividades de la empresa)
            else:
                raise UserError(_('No se pude conectar a DGI para extraer los datos'))
        else:
            raise UserError(_('Solo puede consultar si el partner tiene tipo de identificación RUT'))
