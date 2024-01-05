# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models, api
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools import safe_eval


class L10nUyCfe(models.AbstractModel):

    _inherit = 'l10n.uy.cfe'

    # TODO KZ not sure if we needed
    # company_id = fields.Many2one("res.compaany")

    # TO remove via script
    """
    l10n_uy_cfe_state = fields.Selection([
        ('not_apply', 'Not apply - Not a CFE'),
        ('draft_cfe', 'Draft CFE'),
        # UCFE error states
        ('xml_error', 'ERROR: CFE XML not valid'),
        ('connection_error', 'ERROR: Connection to UCFE'),
        ('ucfe_error', 'ERROR: Related to UCFE'),
    """

    # Campos preparacion y acuseo de recepcion/envio xml

    l10n_uy_cfe_xml = fields.Text('XML CFE', copy=False, groups="base.group_system")
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")

    # Campos resultados almacenamiento de comprobantes emitidos

    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)
    l10n_uy_cfe_pdf = fields.Many2one('ir.attachment', string='CFE PDF Representation', copy=False)

    @api.model
    def l10n_uy_get_ucfe_notif(self):
        # TODO test it

        # 600 - Consulta de Notificacion Disponible
        response = self.env.company._l10n_uy_ucfe_inbox_operation('600')
        # import pdb; pdb.set_trace()

        # If there is notifications
        if response.Resp.CodRta == '00':
            # response.Resp.TipoNotificacion

            # 610 - Solicitud de datos de Notificacion
            response2 = self.company_id._l10n_uy_ucfe_inbox_operation('610', {'idReq': response.Resp.idReq})

            # ('5', 'Aviso de CFE emitido rechazado por DGI'), or
            # ('6', 'Aviso de CFE emitido rechazado por el receptor electrónico'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # MensajeRta

            # ('7', 'Aviso de CFE recibido'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # XmlCfeFirmado
                # Adenda
                # RutEmisor
                # Etiquetas
                # EstadoEnDgiCfeRecibido

            # ('8', 'Aviso de anulación de CFE recibido'),
            # ('9', 'Aviso de aceptación comercial de un CFE recibido'),
            # ('10', 'Aviso de aceptación comercial de un CFE recibido en la gestión UCFE'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # RutEmisor

            # ('11', 'Aviso de que se ha emitido un CFE'),
            # ('12', 'Aviso de que se ha emitido un CFE en la gestión UCFE'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # XmlCfeFirmado
                # Adenda
                # Etiquetas

            # ('13', 'Aviso de rechazo comercial de un CFE recibido'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # MensajeRta
                # RutEmisor

            # ('14', 'Aviso de rechazo comercial de un CFE recibido en la gestión UCFE'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # RutEmisor

            # ('15', 'Aviso de CFE emitido aceptado por DGI'),
            # ('16', 'Aviso de CFE emitido aceptado por el receptor electrónico'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe

            # ('17', 'Aviso que a un CFE emitido se lo ha etiquetado'),
            # ('18', 'Aviso que a un CFE emitido se le removió una etiqueta'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # RutEmisor

            # ('19', 'Aviso que a un CFE recibido se lo ha etiquetado'),
            # ('20', 'Aviso que a un CFE recibido se le removió una etiqueta'),
                # Uuid
                # TipoCfe
                # Serie
                # NumeroCfe
                # RutEmisor
                # Etiquetas

        elif response.Resp.CodRta == '01':
            raise UserError(_('No hay notificaciones disponibles en el UCFE'))
        else:
            raise UserError(_('ERROR: esto es lo que recibimos %s') % response)

        # TODO 620 - Descartar Notificacion
        # response3 = self.company_id._l10n_uy_ucfe_inbox_operation('620', {
        #     'idReq': response.Resp.idReq, 'TipoNotificacion': response.Resp.TipoNotificacion})
        # if response3.Resp.CodRta != '00':
        #     raise UserError(_('ERROR: la notificacion no pudo descartarse %s') % response)

    def action_cfe_inform_commercial_status(self, rejection=False):
        # TODO only applies for vendor bills
        # Código Motivos de rechazo de un CFE DGI Receptor
        rejection_reasons = [
            # DGI Codes
            ('E01', 'Tipo y Nº de CFE ya fue reportado como anulado'),
            ('E02', 'Tipo y Nº de CFE ya existe en los registros'),  # Also Receptor Codes
            ('E03', 'Tipo y Nº de CFE no se corresponden con el CAE'),  # Also Receptor Codes
            ('E04', 'Firma electrónica no es válida'),  # Also Receptor Codes
            ('E05', 'No cumple validaciones (*) de Formato comprobantes'),  # Also Receptor Codes
            ('E07', 'Fecha Firma de CFE no se corresponde con fecha CAE'),  # Also Receptor Codes
            ('E08', 'No coincide RUC de CFE y Complemento Fiscal'),
            ('E09', 'RUC emisor y/o tipo de CFE no se corresponden con el CAE'),

            # Receptor
            ('E20', 'Orden de compra vencida'),
            ('E21', 'Mercadería en mal estado'),
            ('E22', 'Proveedor inhabilitado por organismo de contralor'),
            ('E23', 'Contraprestación no recibida'),
            ('E24', 'Diferencia precios y/o descuentos'),
            ('E25', 'Factura con error cálculos'),
            ('E26', 'Diferencia con plazos'),
            ('E27', ''),
            ('E28', ''),
            ('E29', ''),
            ('E30', ''),
            ('E60', ''),
        ]

        # 410 - Informar aceptación/rechazo comercial de un CFE recibido.
        req_data = {
            'Uuid': self.l10n_uy_cfe_uuid,
            'TipoCfe': int(self.l10n_latam_document_type_id.code),
            'CodRta': '01' if rejection else '00',
        }
        if rejection:
            # TODO let the user to select a rejection reason and code
            req_data['RechCom'] = [(rejection_reasons[1][0], rejection_reasons[1][1])]
            # TODO
            # Es una lista de hasta 30 registros con dos campos:
            # • Código de rechazo de 3 posiciones. Los códigos posibles son E01 a E60 según define DGI.
            # • Descripción del código de rechazo (glosa) de 50 posiciones.
            # Cada registro tiene 53 posiciones fijas, pueden llegar hasta 30 registros por lo que el largo total del campo es de 1590 posiciones.

        response = self.company_id._l10n_uy_ucfe_inbox_operation('410', req_data)
        if response.Resp.CodRta != '411':
            raise UserError(_('No se pudo procesar la aceptación/rechazo comerncial'))
        # import pdb; pdb.set_trace()

    def _get_report_params(self):
        """ REPORTE PERSONALIZADO """
        adenda = self._l10n_uy_get_cfe_adenda().get('Adenda')
        if not adenda and len(adenda) < 799:
            #En caso de que el cliente eliga el reporte que quiere imprimir
            report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or '[]')

        return report_params

    def action_l10n_uy_get_pdf(self):
        """ Solo permitir crear PDF cuando este aun no existe,y grabar en campo binario """
        # TODO KZ toca poner a prueba
        self.ensure_one()
        if not self.l10n_uy_cfe_pdf:
            res = super().action_l10n_uy_get_pdf()
            self.l10n_uy_cfe_pdf = self.env['ir.attachment'].browse(res.get('url').split('ir.attachment&id=')[-1]
)
        return res

    def action_l10n_uy_validate_cfe(self):
        """ Be able to validate a cfe """
        self._l10n_uy_vaidate_cfe(self.sudo().l10n_uy_cfe_xml, raise_exception=True)

    def action_l10n_uy_preview_xml(self):
        """ Be able to show preview of the CFE to be send """
        self.l10n_uy_cfe_xml = self._l10n_uy_create_cfe().get('cfe_str')

    def set_any_extra_field(self, data):
        self.l10n_uy_cfe_xml = data.get('CfeXmlOTexto')
        transport = data.get('transport')
        self.l10n_uy_dgi_xml_response = transport.xml_response
        self.l10n_uy_dgi_xml_request = transport.xml_request

    # * 00 y 11, el CFE ha sido aceptado (con el 11 aún falta la confirmación definitiva de DGI).
    # El punto de emisión no debe volver a enviar el documento.
    # Se puede consultar el estado actual de un CFE para el que se recibió 11 con los mensajes de consulta
    # disponibles.
    # • 01 y 05 son rechazos. Cuando rechaza DGI se recibe 05 e implica que quedó anulado el documento.
    # El punto de emisión no debe volver a enviar el comprobante ni tampoco enviar una nota de crédito
    # para comenzar.
    # * 03 y 89, indican un problema de configuración en UCFE.
    # El punto de emisión debe enviar de nuevo el CFE luego de que el administrador configure correctamente
    # los parámetros
    # • 12, 94 y 99 no se van a recibir.
    # • 30, falta algún campo requerido para el mensaje que se está enviando. Requiere estudio técnico, el punto de emisión no debe volver a enviar el documento hasta que no se solucione el problema.
    # • 31, error de formato en el CFE pues se encuentra mal armado el XML. Requiere estudio técnico, el punto de emisión no debe volver a enviar el documento hasta que no se solucione el problema.
    # • 96, error interno en UCFE (por ejemplo bug, motor de base de datos caído, disco lleno, etc.). Requiere soporte técnico, el punto de emisión debe enviar de nuevo el CFE cuando se solucione el problema

    # TODO este viene vacio, ver cuando realmente es seteado para asi setearlo en este momento
    # Tambien tenemos ver para que sirve 'DatosQr': 'https://www.efactura.dgi.gub.uy/consultaQRPrueba/cfe?218435730016,101,A,1,18.00,17/09/2020,gKSy8dDHR0YsTy0P4cx%2bcSu4Zvo%3d',
    # self.l10n_uy_dgi_barcode = response.Resp.ImagenQr
    # TODO evaluate if this is usefull to put it in a record place?
    # 'Adenda': None,
    # 'CodigoSeguridad': 'gKSy8d',
    # 'EstadoSituacion': None,
    # 'Etiquetas': None,
    # 'FechaFirma': '2020-09-17T19:50:50.0000000-03:00',
    # 'IdCae': '90200001010',
    # 'IdReq': '1',
    # 'RutEmisor': None,

    # ??? – Recepcion de CFE en UCFE
    # ??? – Conversion y validation
    # TODO comprobar. este devolvera un campo clave llamado UUID que permite identificar el comprobante, si es enviando dos vence sno genera otro CFE firmado
