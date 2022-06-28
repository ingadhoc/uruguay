# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _, api
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr
from odoo.tools.safe_eval import safe_eval
from . import ucfe_errors
from datetime import datetime
from html import unescape
import re
import base64
import stdnum.uy
import logging


_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = "account.move"

    l10n_uy_cfe_state = fields.Selection([
        ('not_apply', 'Not apply - Not a CFE'),
        ('draft_cfe', 'Draft CFE'),

        # DGI states
        ('received', 'Waiting response from DGI'),
        ('accepted', 'CFE Accepted by DGI'),
        ('rejected', 'CFE Rejected by DGI'),

        # TODO not sure I think we will remove this
        ('ui_indexada', 'CFE Not sent, amount bellow 10.000 UI'),

        # UCFE error states
        ('xml_error', 'ERROR: CFE XML not valid'),
        ('connection_error', 'ERROR: Connection to UCFE'),
        ('ucfe_error', 'ERROR: Related to UCFE'),
        ],
        string='CFE Status', copy=False, readonly=True, track_visibility='onchange',
        help="If 'ERROR: Related to UCFE' please check details of 'UCFE State'")

    l10n_uy_journal_type = fields.Selection(related='journal_id.l10n_uy_type')

    l10n_uy_cfe_dgi_state = fields.Selection([
        ('00', '00 - aceptado por DGI'),
        ('05', '05 - rechazado por DGI'),
        ('06', '06 - observado por DGI'),
        ('11', '11 - UCFE no pudo consultar a DGI (puede intentar volver a ejecutar la consulta con la función 650 – Consulta a DGI por CFE recibido)'),
        ('10', '10 - aceptado por DGI pero no se pudo ejecutar la consulta QR'),
        ('15', '15 - rechazado por DGI pero no se pudo ejecutar la consulta QR'),
        ('16', '16 - observado por DGI pero no se pudo ejecutar la consulta QR'),
        ('20', '20 - aceptado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
        ('25', '25 - rechazado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
        ('26', '26 - observado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
    ], 'Vendor Bill DGI State', copy=False, readonly=True, track_visibility='onchange')  # EstadoEnDgiCfeRecibido

    l10n_uy_ucfe_state = fields.Selection([
        ('00', '00 - Petición aceptada y procesada'),
        ('01', '01 - Petición denegada'),
        ('03', '03 - Comercio inválido'),
        ('05', '05 - CFE rechazado por DGI'),
        ('06', '06 - CFE observado por DGI'),
        ('11', '11 - CFE aceptado por UCFE, en espera de respuesta de DGI'),
        ('12', '12 - Requerimiento inválido'),
        ('30', '30 - Error en formato'),
        ('31', '31 - Error en formato de CFE'),
        ('89', '89 - Terminal inválida'),
        ('96', '96 - Error en sistema'),
        ('99', '99 - Sesión no iniciada'),
    ], 'UCFE State', copy=False, readonly=True, track_visibility='onchange')  # CodRta

    l10n_uy_ucfe_msg = fields.Text('UCFE Mensaje de Respuesta', copy=False, readonly=True, track_visibility='onchange')  # MensajeRta

    l10n_uy_ucfe_notif = fields.Selection([
        ('5', 'Aviso de CFE emitido rechazado por DGI'),
        ('6', 'Aviso de CFE emitido rechazado por el receptor electrónico'),
        ('7', 'Aviso de CFE recibido'),
        ('8', 'Aviso de anulación de CFE recibido'),
        ('9', 'Aviso de aceptación comercial de un CFE recibido'),
        ('10', 'Aviso de aceptación comercial de un CFE recibido en la gestión UCFE'),
        ('11', 'Aviso de que se ha emitido un CFE'),
        ('12', 'Aviso de que se ha emitido un CFE en la gestión UCFE'),
        ('13', 'Aviso de rechazo comercial de un CFE recibido'),
        ('14', 'Aviso de rechazo comercial de un CFE recibido en la gestión UCFE'),
        ('15', 'Aviso de CFE emitido aceptado por DGI'),
        ('16', 'Aviso de CFE emitido aceptado por el receptor electrónico'),
        ('17', 'Aviso que a un CFE emitido se lo ha etiquetado'),
        ('18', 'Aviso que a un CFE emitido se le removió una etiqueta'),
        ('19', 'Aviso que a un CFE recibido se lo ha etiquetado'),
        ('20', 'Aviso que a un CFE recibido se le removió una etiqueta'),
        ], 'UCFE Tipo de Notificacion', copy=False, readonly=True, track_visibility='onchange')  # TipoNotificacion

    l10n_uy_cfe_uuid = fields.Char(
        'Clave o UUID del CFE', help="Unique identification per CFE in UCFE. Currently is formed by the concatenation"
        " of model name + record id + date", copy=False)
    # TODO este numero debe ser maximo 36 caracteres máximo. esto debemos mejorarlo

    l10n_uy_cfe_sale_mod = fields.Selection([
        ('1', 'Régimen General'),
        ('2', 'Consignación'),
        ('3', 'Precio Revisable'),
        ('4', 'Bienes propios a exclaves aduaneros'),
        ('90', 'Régimen general- exportación de servicios'),
        ('99', 'Otras transacciones'),
    ], 'Modalidad de Venta', help="Este campo debe enviarse cuando se reporta un CFE de tipo e-Facutra de Exportación")
    l10n_uy_cfe_transport_route = fields.Selection([
        ('1', 'Marítimo'),
        ('2', 'Aéreo'),
        ('3', 'Terrestre'),
        ('8', 'N/A'),
        ('9', 'Otro'),
    ], 'Vía de Transporte', help="Este campo debe enviarse cuando se reporta un CFE de tipo e-Facutra de Exportación")
    l10n_uy_cfe_xml = fields.Text('XML CFE', copy=False, groups="base.group_system")
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")

    # TODO not sure this fields are going to make it
    l10n_uy_dgi_acceptation_status = fields.Selection([
        ('received', 'Received'),
        ('ack_sent', 'Acknowledge Sent'),
        ('claimed', 'Claimed'),
        ('accepted', 'Accepted'),
    ], string='CFE Accept status', copy=False, readonly=True, help="""The status of the CFE Acceptation
    * Received: the DTE was received by us for vendor bills, by our customers for customer invoices.
    * Acknowledge Sent: the Acknowledge has been sent to the vendor.
    * Claimed: the DTE was claimed by us for vendor bills, by our customers for customer invoices.
    * Accepted: the DTE was accepted by us for vendor bills, by our customers for customer invoices.
    """)
    l10n_uy_cfe_partner_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
    ], string='CFE Partner Status', readonly=True, copy=False, help="""
    Status of sending the CFE to the partner:
    - Not sent: the CFE has not been sent to the partner but it has sent to DGI.
    - Sent: The CFE has been sent to the partner.""")
    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)
    l10n_uy_cfe_pdf = fields.Many2one('ir.attachment', string='CFE PDF Representation', copy=False)

    # This is required to be able to save defaults taking into account the document type selected
    l10n_latam_document_type_id = fields.Many2one(change_default=True)

    # Buttons

    def action_invoice_cancel(self):
        # TODO funcionando para facturas de clientes, ver para facturas de proveedor
        uy_sale_docs = self.filtered(lambda x: x.company_id.country_id.code == 'UY' and x.is_sale_document(include_receipts=True))
        for record in uy_sale_docs:
            # The move cannot be modified once has been sent to UCFE
            if record.l10n_uy_ucfe_state in record._uy_invoice_already_sent():
                raise UserError(_('This %s has been already sent to UCFE. It cannot be cancelled. '
                                  'You can only click Consult DGI State to update.') % record.l10n_latam_document_type_id.name)
            # The move cannot be modified once the CFE has been accepted by the DGI
            elif record.l10n_uy_ucfe_state == '00':
                raise UserError(_('This %s is accepted by DGI. It cannot be cancelled. '
                                  'Instead you should revert it.') % record.l10n_latam_document_type_id.name)
            # record.l10n_cl_dte_status = 'cancelled'
        return super().action_invoice_cancel()

    @api.model
    def _uy_invoice_already_sent(self):
        """ Invoices that have any of this ufce_status can not be sent again to ucfe because they can not be changed

        - 00: Petición aceptada y procesada
        - 05: CFE rechazado por DGI
        - 06: CFE observado por DGI
        - 11: CFE aceptado por UCFE, en espera de respuesta de DGI """
        return ['00', '05', '06', '11']

    # TODO 14.0 change to _post or action_post
    def post(self):
        """ After validate the invoices in odoo we send it to dgi via ucfe """
        res = super().post()

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and
            x.is_invoice() and
            x.journal_id.l10n_uy_type in ['electronic', 'contingency'] and
            x.l10n_uy_ucfe_state not in x._uy_invoice_already_sent() and
            # TODO possible we are missing electronic documents here, review the
            int(x.l10n_latam_document_type_id.code) > 100)

        # Esto es para evitar que puedan crear facturas de contingencia desde el Odoo, para poder soportarlo tenemos
        # que integrar la lógica de manejar el CAE desde el lado de Odoo, enviar info de numero de serie, numero a usar
        # etc en el xml para que sea un XML valido. Una vez que este implementado esta parte se puede ir.
        if uy_invoices.filtered(lambda x: x.journal_id.l10n_uy_type == 'contingency'):
            raise UserError(_('Las facturas de Contingencia aun no están implementadas en el Odoo, para crear facturas'
                              ' de contingencia por favor generarla directamente desde al Uruware y luego cargar en el'
                              ' Odoo'))

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_invoices.filtered(lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_inv()
            uy_invoices = uy_invoices - pre_validated_in_uruware

        if not uy_invoices:
            return res

        # Send invoices to DGI and get the return info
        for inv in uy_invoices:

            # Set the invoice rate
            if inv.company_id.currency_id == inv.currency_id:
                currency_rate = 1.0
            else:
                currency_rate = inv.currency_id._convert(
                    1.0, inv.company_id.currency_id, inv.company_id, inv.date or fields.Date.today(), round=False)
            inv.l10n_uy_currency_rate = currency_rate

            if inv._is_dummy_dgi_validation():
                inv._dummy_dgi_validation()
                continue

            # TODO KZ I think we can avoid this loop. review
            inv._l10n_uy_dgi_post()

        return res

    def _is_dummy_dgi_validation(self):
        # If we are on testing environment and we don't have ucfe configuration we validate only locally.
        # This is useful when duplicating the production database for training purpose or others
        self.ensure_one()
        return self.company_id._uy_get_environment_type() == 'testing' and \
            not self.company_id.sudo()._is_connection_info_complete(raise_exception=False)


    def action_l10n_uy_get_uruware_inv(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,
        Nos permite extraer la info del comprobante que fue emitido desde uruware y que no esta en Odoo para asi
        quede la info de numero de documento tipo de documento estado del comprobante"""
        uy_docs = self.env['l10n_latam.document.type'].search([('country_id.code', '=', 'UY')])
        for inv in self:
            if not inv.l10n_uy_cfe_uuid:
                raise UserError(_('Necesita definir "Clave o UUID del CFE" para poder continuar'))
            if 'error' in inv.l10n_uy_cfe_state:
                raise UserError(_('No se puede obtener la factura de un comprobante con error'))
            # TODO en este momento estamos usando este 360 porque es el que tenemos pero estamos esperando respuesta de
            # soporte uruware a ver como podemos extraer mas información y poder validarla.
            response = inv.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': inv.l10n_uy_cfe_uuid})
            inv.write({
                'l10n_latam_document_number': response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe),
                'l10n_latam_document_type_id': uy_docs.filtered(lambda x: x.code == response.Resp.TipoCfe).id,
                'l10n_uy_ucfe_state': response.Resp.CodRta,
                'l10n_uy_ucfe_msg': response.Resp.MensajeRta,
            })
            inv._update_l10n_uy_cfe_state()
            # TODO Improve add logic:
            # 1. add information to the cfe xml
            # 2. cfe another data
            # 3. validation that is the same invoice

    def action_l10n_uy_get_dgi_state(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,
        Toma solo aquellos comprobantes que están en esperado respuesta de DGI y consulta en el UFCE si DGI devolvio
        respuesta acerca del comprobante

        TODO esto solo aplica a facturas de clientes, implementar facturas de proveedor 650

        NOTA: Esto aplica solo para comprobantes emitidos, es distinta la consulta para comprobantes recibidos"""
        for rec in self.filtered(lambda x: x.l10n_uy_cfe_state == 'received'):
            response = rec.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': rec.l10n_uy_cfe_uuid})
            values = {
                'l10n_uy_ucfe_state': response.Resp.CodRta,
                'l10n_uy_ucfe_msg': response.Resp.MensajeRta,
                'l10n_uy_ucfe_notif': response.Resp.TipoNotificacion,
            }
            values = dict([(key, val) for key, val in values.items() if val])
            rec.write(values)
            rec._update_l10n_uy_cfe_state()

    # TODO not working review why
    # @api.onchange('journal_id', 'state')
    # def _onchange_l10n_uy_cfe_state(self):
    #     if self.state == 'draft' and not self.l10n_uy_ucfe_state:
    #         if self.l10n_uy_journal_type not in ['electronic', 'contingency']:
    #             return 'not_apply'
    #         return 'draft_cfe'
    #     return False

    def _amount_total_company_currency(self):
        """ TODO search if Odoo already have something to do exactly the same as here """
        self.ensure_one()
        return self.amount_total if self.currency_id == self.company_currency_id else self.currency_id._convert(
            self.amount_total, self.company_id.currency_id, self.company_id, self.date or fields.Date.today(), round=False)

    def _update_l10n_uy_cfe_state(self):
        """ Update the CFE State show to the user depending of the information of the UFCE and DGI State return from
        third party service.

        * Customer Invoice (l10n_uy_ucfe_state = CodRta)
        * Bill (l10n_uy_cfe_dgi_state = EstadoEnDgiCfeRecibido) this last one not implemented yet

        More important:
            00 es que el comprobante fue aceptado,
            11 es "Esperando respuesta de DGI",
            01 es rechazado por UCFE
            05 rechazado por DGI."""
        self.ensure_one()
        ucfe_state = self.l10n_uy_ucfe_state
        if not ucfe_state:
            return

        match = {
            '00': 'accepted',
            '11': 'received',
            '01': 'ucfe_error',
            '05': 'rejected',
            '03': 'ucfe_error',
            '89': 'ucfe_error',

            '12': 'ucfe_error',
            '94': 'ucfe_error',
            '99': 'ucfe_error',

            '30': 'ucfe_error',
            '31': 'xml_error',
            '96': 'ucfe_error',
        }
        self.l10n_uy_cfe_state = match.get(ucfe_state)

    def action_l10n_uy_validate_cfe(self):
        """ Be able to validate a cfe """
        self._l10n_uy_vaidate_cfe(self.sudo().l10n_uy_cfe_xml, raise_exception=True)

    def action_l10n_uy_get_pdf(self):
        """ call query webservice to print pdf format of the invoice
        7.1.9 Representación impresa estándar de un CFE emitido en formato PDF

        return: create attachment in the move and automatica download """
        # TODO cada vez que corremos intenta imprimir el existente, borrar el attachment para volver a generar
        if not self.l10n_uy_cfe_pdf:
            if 'out' in self.type:
                rut_field = 'rut'
                rut_value = self.company_id.partner_id.vat
            elif 'in' in self.type:
                # TODO esto no se ha probado aun
                rut_field = 'rutRecibido'
                rut_value = self.partner_id.vat
            else:
                raise UserError(_('No se puede imprimir la representación Legal de este documento'))
            document_number = re.search(r"([A-Z]*)([0-9]*)", self.l10n_latam_document_number).groups()
            req_data = {
                rut_field: rut_value,
                'tipoCfe': int(self.l10n_latam_document_type_id.code),
                'serieCfe': document_number[0],
                'numeroCfe': document_number[1],
            }
            response = self.company_id._l10n_uy_ucfe_query('ObtenerPdf', req_data)
            self.l10n_uy_cfe_pdf = self.env['ir.attachment'].create({
                'name': (self.name or 'INV').replace('/', '_') + '.pdf',
                'res_model': self._name, 'res_id': self.id,
                'type': 'binary', 'datas': base64.b64encode(response)
            })
        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=ir.attachment&id=" + str(self.l10n_uy_cfe_pdf.id) +
            "&filename_field=name&field=datas&download=true&name=" + self.l10n_uy_cfe_pdf.name,
            'target': 'self'
        }

    def _l10n_uy_validate_company_data(self):
        for company in self.sudo().mapped('company_id'):
            errors = []

            if not company.vat:
                errors.append(_('Set your company RUT'))
            else:
                # Validate if the VAT is a valid RUT
                # TODO move this to check_vat?
                try:
                    stdnum.uy.rut.validate(company.vat)
                except Exception as exp:
                    errors.append(_('Set a valid RUT in your company') + ': ' + str(exp))

            if not company.l10n_uy_dgi_house_code:
                errors.append(_('Set your company House Code'))
            if not company.state_id:
                errors.append(_('Set your company state'))
            if not company.city:
                errors.append(_('Set your company city'))

            if errors:
                raise UserError(_('In order to create the CFE document first need to complete your company data:\n- ')
                                + '\n- '.join(errors))

    # Main methods

    def _l10n_uy_dgi_post(self):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """

        self._l10n_uy_validate_company_data()
        for inv in self:
            now = datetime.utcnow()
            CfeXmlOTexto = inv._l10n_uy_create_cfe().get('cfe_str')
            req_data = {
                'Uuid': 'account.move-' + str(inv.id) + '_' + str(fields.Datetime.now()),  # TODO this need to be improve
                'TipoCfe': int(inv.l10n_latam_document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto}

            req_data.update(inv._l10n_uy_get_cfe_adenda())
            req_data.update(inv._l10n_uy_get_cfe_serie())
            response, transport = inv.company_id._l10n_uy_ucfe_inbox_operation('310', req_data, return_transport=1)

            inv = inv.sudo()
            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()

            # Si conseguimos un error de factura electronica directamente hacemos rollback: para que la factura de odoo
            # quede en borrador y no tengamos quede posteada y tengamos que cancelarla luego
            if 'error' in inv.l10n_uy_cfe_state:
                self.env.cr.rollback()

            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()
            inv.l10n_uy_cfe_xml = CfeXmlOTexto
            inv.l10n_uy_dgi_xml_response = transport.xml_response
            inv.l10n_uy_dgi_xml_request = transport.xml_request
            inv.l10n_uy_cfe_uuid = response.Resp.Uuid
            inv.l10n_uy_ucfe_msg = response.Resp.MensajeRta
            inv.l10n_uy_ucfe_notif = response.Resp.TipoNotificacion

            if response.Resp.CodRta not in inv._uy_invoice_already_sent():
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
                return

            # If everything is ok we save the return information
            inv.l10n_latam_document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)

            # TODO this one is failing, review why
            inv.l10n_uy_cfe_file = self.env['ir.attachment'].create({
                'name': 'CFE_{}.xml'.format(inv.l10n_latam_document_number),
                'res_model': self._name, 'res_id': inv.id,
                'type': 'binary', 'datas': base64.b64encode(CfeXmlOTexto.encode('ISO-8859-1'))}).id

            # If the invoice has been posted automatically print and attach the legal invoice reporte to the record.
            if 'error' not in inv.l10n_uy_cfe_state:
                inv.action_l10n_uy_get_pdf()

            # TODO este viene vacio, ver cuando realmente es seteado para asi setearlo en este momento
            # Tambien tenemos ver para que sirve 'DatosQr': 'https://www.efactura.dgi.gub.uy/consultaQRPrueba/cfe?218435730016,101,A,1,18.00,17/09/2020,gKSy8dDHR0YsTy0P4cx%2bcSu4Zvo%3d',
            # self.l10n_uy_dgi_barcode = response.Resp.ImagenQr
            # TODO evaluate if this is usefull to put it in a invoice place?
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

        return response

    # Helpers

    def _dummy_dgi_validation(self):
        """ Only when we want to skip DGI validation in testing environment. Fill the DGI result  fields with dummy
        values in order to continue with the invoice validation without passing to DGI validations s"""
        # TODO need to update to the result we need, all the fields we need to add are not defined yet
        self.write({
            'l10n_uy_cfe_uuid': '123456',
        })
        self.message_post(body=_('Validated locally because is not Uruware parameters are not properly configured'))

    # TODO Consulta si un RUT es emisor electrónico 630 / 631
    # TODO RUT consultado a DGI (función 640 – Consulta a DGI por datos de RUT)

    def _l10n_uy_get_cfe_item_detail(self):
        """ Devuelve una lista con los datos que debemos informar por linea de factura en el CFE """
        res = []
        # e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección: Hasta 700
        if self.l10n_latam_document_type_id.code in [101, 102, 103, 131, 132, 133] and len(self.invoice_line_ids) > 700:
            raise UserError('Para e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección solo puede'
                            ' reportar Hasta 700')
        # Otros CFE: Hasta 200
        elif len(self.invoice_line_ids) > 200:
            raise UserError('Para este tipo de CFE solo puede reportar hasta 200 lineas')

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        for k, line in enumerate(self.invoice_line_ids, 1):
            res.append({
                'NroLinDet': k,  # B1 No de línea o No Secuencial. a partir de 1
                'IndFact': line._l10n_uy_get_cfe_indfact(),  # B4 Indicador de facturación
                'NomItem': line.name[:80],  # B7 Nombre del ítem (producto o servicio). Maximo 80 caracteres

                'Cantidad': line.quantity,  # B9 Cantidad. NUM 17
                # TODO OJO se admite negativo? desglozar
                # TODO Valor numerico 14 enteros y 3 decimales. debemos convertir el formato a representarlo

                'UniMed': line.product_uom_id.name[:4] if line.product_uom_id else 'N/A',  # B10 Unidad de medida

                'PrecioUnitario': float_repr(line._get_price_total_and_subtotal(quantity=1)['price_subtotal'], 6),  # B11 Precio unitario
                'MontoItem': float_repr(line.price_subtotal, 2),  # B24 Monto Item
                # TODO en futuro para incluir descuentos B24=(B9*B11)–B13+B17
            })

        return res

    @api.model
    def _l10n_uy_get_min_by_unidad_indexada(self):
        return self.env.ref('l10n_uy_account.UYI').rate * 10000

    def is_expo_cfe(self):
        """ True of False in the current invoice is an exporation invoice type """
        self.ensure_one()
        return int(self.l10n_latam_document_type_id.code) in [121, 122, 123]

    def _l10n_uy_get_cfe_receptor(self):
        self.ensure_one()
        res = {}
        document_type = int(self.l10n_latam_document_type_id.code)
        cond_e_fact = document_type in [111, 112, 113, 141, 142, 143]
        cond_e_ticket = document_type in [101, 102, 103, 131, 132, 133] and self._amount_total_company_currency() > self._l10n_uy_get_min_by_unidad_indexada()
        cond_e_boleta = document_type in [151, 152, 153]
        cond_e_contg = document_type in [201, 202, 203]
        cond_e_fact_expo = self.is_expo_cfe()

        if cond_e_fact or cond_e_ticket or cond_e_boleta or cond_e_contg or cond_e_fact_expo:
            # cond_e_fact: obligatorio RUC (C60= 2).
            # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E), debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).


            if not self.partner_id.l10n_latam_identification_type_id and not self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code:
                raise UserError(_('The partner of the invoice need to have a Uruguayan Identification Type'))

            tipo_doc = int(self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code)
            cod_pais = 'UY' if tipo_doc in [2, 3] else '99'

            if tipo_doc == 0:
                raise UserError(_('Debe indicar un tipo de documento Uruguayo para poder facturar a este cliente'))
            res.update({
                # TODO -Free Shop: siempre se debe identificar al receptor.
                'TipoDocRecep': tipo_doc,  # C60
                'CodPaisRecep': self.partner_id.country_id.code or cod_pais,   # C61
                'DocRecep' if tipo_doc in [1, 2, 3] else 'DocRecepExt': self.partner_id.vat,  # C62 / C62.1
            })

            if cond_e_fact_expo or cond_e_fact or cond_e_ticket:
                if not all([self.partner_id.street, self.partner_id.city, self.partner_id.state_id, self.partner_id.country_id, self.partner_id.vat]):
                    msg = _('Debe configurar la dirección, ciudad, provincia, pais del receptor y número de identificación')
                    if cond_e_ticket:
                        msg += '\n' + _('E-ticket needs these values because that total amount > 10.000 * Unidad Indexada Uruguaya')
                    raise UserError(msg)
                res.update({
                    'RznSocRecep': self.partner_id.name,  # C63
                    'DirRecep': (self.partner_id.street + (' ' + self.partner_id.street2 if self.partner_id.street2 else ''))[:70],
                    'CiudadRecep': self.partner_id.city[:30],
                    'DeptoRecep': self.partner_id.state_id.name[:30],
                    'PaisRecep': self.partner_id.country_id.name,
                })

        return res

    def _l10n_uy_get_cfe_tag(self):
        self.ensure_one()
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code in [101, 102, 103, 201]:
            return 'eTck'
        elif cfe_code in [111, 112, 113]:
            return 'eFact'
        elif cfe_code in [121, 122, 123]:
            return 'eFact_Exp'
        else:
            raise UserError('Este Comprobante aun no ha sido implementado')

    def _l10n_uy_get_cfe_adenda(self):
        self.ensure_one()
        adenda = ''
        for rec in self.company_id.l10n_uy_adenda_ids:
            if bool(safe_eval(rec.condition, {'inv': self})) == True:
                adenda +=  "\n\n" + rec.content

        # Si el comprobante/factura tiene una referencia entonces agregarla para que se muestre al final de la Adenda
        if self.ref:
            adenda += "\n\nReferencia: %s" % self.ref

        if adenda:
            return {'Adenda': adenda.strip()}
        return {}

    def _l10n_uy_get_cfe_serie(self):
        """ Si soy ticket de contingencia usar los valores que estan definidos en el Odoo """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res

    def _l10n_uy_get_cfe_referencia(self):
        res = []
        # If is a debit/credit note cfe then we need to inform el tag referencia
        if self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note']:
            related_cfe = self._uy_found_related_invoice()
            if not related_cfe:
                raise UserError(_('Para validar una ND/NC debe informar el Documento de Origen'))
            for k, related_cfe in enumerate(self._uy_found_related_invoice(), 1):
                document_number = re.search(r"([A-Z]*)([0-9]*)", related_cfe.l10n_latam_document_number).groups()

                tpo_doc_ref = int(related_cfe.l10n_latam_document_type_id.code)
                if not tpo_doc_ref:
                    raise UserError(_('Para validar una ND/NC debe informar el Documento de Origen y este debe ser'
                                      ' también electrónico'))
                res.append({
                    'NroLinRef': k,
                    'TpoDocRef': tpo_doc_ref,
                    'Serie': document_number[0],
                    'NroCFERef': document_number[1],
                    # 'FechaCFEref': 2015-01-31, TODO inform?
                })
        return res

    # TODO I think this 3 methods can be merged in one?

    def _l10n_uy_get_cfe_caluventa(self):
        if not self.invoice_incoterm_id:
            raise UserError(_('Para reportar factura de exportación debe indicar el incoterm correspondiente.'
                ' Puede indicar este valor en el tab Otra Información'))
        return self.invoice_incoterm_id.code

    def _l10n_uy_get_cfe_modventa(self):
        if not self.l10n_uy_cfe_sale_mod:
            raise UserError(_(
                'Para reportar facturas de exportación debe indicar la Modalidad de Venta correspondiente.'
                ' Puede indicar este valor en el tab Otra Información'))
        return int(self.l10n_uy_cfe_sale_mod)

    def _l10n_uy_get_cfe_viatransp(self):
        if not self.l10n_uy_cfe_transport_route:
            raise UserError(_('Para reportar facturas de exportación debe indicar la Via de Transporte correspondiente.'
                ' Puede indicar este valor en el tab Otra Información'))
        return int(self.l10n_uy_cfe_transport_route)

    def _l10n_uy_get_cfe_iddoc(self):
        self.ensure_one()
        res = {
            'FmaPago': 1 if self.l10n_uy_payment_type == 'cash' else 2,
            'FchEmis': self.date.strftime('%Y-%m-%d'),
        }
        if self.is_expo_cfe():
            res.update({
                'ModVenta': self._l10n_uy_get_cfe_modventa(),
                'ClauVenta': self._l10n_uy_get_cfe_caluventa(),
                'ViaTransp':  self._l10n_uy_get_cfe_viatransp(),
            })
        res.update(self._l10n_uy_get_cfe_serie())
        return res

    def _l10n_uy_create_cfe(self):
        """ Create the CFE xml estructure and validate it
            :return: A dictionary with one of the following key:
            * cfe_str: A string of the unsigned cfe.
            * error: An error if the cfe was not successfully generated. """

        self.ensure_one()
        values = {
            'move': self,
            'RUCEmisor': stdnum.uy.rut.compact(self.company_id.vat),
            'IdDoc': self._l10n_uy_get_cfe_iddoc(),
            'item_detail': self._l10n_uy_get_cfe_item_detail(),
            'totals_detail': self._l10n_uy_get_cfe_totals(),
            'receptor': self._l10n_uy_get_cfe_receptor(),
            'cfe_tag': self._l10n_uy_get_cfe_tag(),
            'referencia_lines': self._l10n_uy_get_cfe_referencia(),
        }
        cfe = self.env.ref('l10n_uy_edi.cfe_template').render(values)
        cfe = unescape(cfe.decode('utf-8')).replace(r'&', '&amp;')
        cfe = '\n'.join([item for item in cfe.split('\n') if item.strip()])

        self._l10n_uy_vaidate_cfe(cfe)
        return {'cfe_str': cfe}

    def _l10n_uy_vaidate_cfe(self, cfe, raise_exception=False):
        # Check CFE XML valid files: 350: Validación de estructura de CFE
        response = self.company_id._l10n_uy_ucfe_inbox_operation('350', {'CfeXmlOTexto': cfe})
        if response.Resp.CodRta != '00':
            # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
            # response.Resp.MensajeRta
            if raise_exception:
                raise UserError('Error al crear el XML del CFẸ\n\n' + ucfe_errors._hint_msg(response))
            # return {'errors': str(e).split('\\n')}

    def _l10n_uy_get_currency(self):
        """ Devuelve el codigo de la moneda del comprobante:
        * Si no hay devuelve el de la compañia.
        * Si la moneda de la compañia no esta configurada entonces lanza un error al usuario.
        * Si la moneda no esta en las monedas defindas en DGI le indica error al usuario """
        self.ensure_one()
        partial_iso4217 = ['ARS', 'BRL', 'CAD', 'CLP', 'CNY', 'COP', 'EUR', 'JPY', 'MXN', 'PYG', 'PEN', 'USD', 'UYU',
                           'VEF']
        # TODO crear estas monedas en el sistema por defecto?
        # * UYI Unidad Indexada uruguaya
        # * UYR Unidad Reajustable uruguaya
        other_currencies = ['UYI', 'UYR']

        currency_name = self.currency_id.name if self.currency_id else self.company_id.currency_id.name
        if not currency_name:
            raise UserError('Debe configurar la moneda de la compañía')
        if currency_name not in partial_iso4217 + other_currencies:
            raise UserError('Esta moneda no existe en la tabla de monedas de la DGI %s' % currency_name)

        return currency_name

    def _l10n_uy_get_cfe_totals(self):
        self.ensure_one()
        res = {}
        res.update({
            'TpoMoneda': self._l10n_uy_get_currency(),  # A-C110 Tipo moneda transacción
            # TODO A-C124? Total Monto Total SUM(A121:A123)
            'MntTotal': float_repr(self.amount_total, 2),
            'CantLinDet': len(self.invoice_line_ids),  # A-C126 Lineas
            'MntPagar': float_repr(self.amount_total, 2),  # A-C130 Monto Total a Pagar
        })

        # C111 Tipo de Cambio
        if self._l10n_uy_get_currency() != 'UYU':
            res['TpoCambio'] = float_repr(self.l10n_uy_currency_rate, 3)
            if self.l10n_uy_currency_rate <= 1.0:
                raise UserError(_('Not valid Currency Rate, need to be greather that 0 in order to be accepted by DGI'))

        if self.is_expo_cfe():
            res.update({
                'MntExpoyAsim': float_repr(self.amount_total, 2),  # C113
            })

        # TODO esto se puse feo..revisar que este bien balance y amount_total
        #     if any(tax.tax_group_id.l10n_ar_vat_afip_code and tax.tax_group_id.l10n_ar_vat_afip_code not in ['0', '1', '2'] for tax in line.tax_line_id) and line[amount_field]:
        #         vat_taxable |= line
        # for vat in vat_taxable:
        #     base_imp = sum(self.invoice_line_ids.filtered(lambda x: x.tax_ids.filtered(lambda y: y.tax_group_id.l10n_ar_vat_afip_code == vat.tax_line_id.tax_group_id.l10n_ar_vat_afip_code)).mapped(amount_field))

        # TODO this need to be improved, using a different way to print the tax information
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes(self.company_id)
        self._check_uruguayan_invoices()

        amount_field = 'price_subtotal'
        tax_line_exempt = self.line_ids.filtered(lambda x: tax_vat_exempt in x.tax_ids)
        if tax_line_exempt and not self.is_expo_cfe():
            res.update({
                'MntNoGrv': float_repr(sum(tax_line_exempt.mapped(amount_field)), 2),  # A112 Total Monto - No Gravado
            })

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        tax_line_basica = self.line_ids.filtered(lambda x: tax_vat_22 in x.tax_line_id)
        if tax_line_basica:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_22 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C117 Total Monto Neto - IVA Tasa Basica
                    'MntNetoIVATasaBasica': float_repr(abs(base_imp), 2),
                    # A120 Tasa Mínima IVA TODO
                    'IVATasaBasica': 22,
                    # A-C122 Total IVA Tasa Básica? Monto del IVA Tasa Basica
                    'MntIVATasaBasica': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        tax_line_minima = self.line_ids.filtered(lambda x: tax_vat_10 in x.tax_line_id)
        if tax_line_minima:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_10 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C116 Total Monto Neto - IVA Tasa Minima
                    'MntNetoIvaTasaMin': float_repr(abs(base_imp), 2),
                    # A119 Tasa Mínima IVA TODO
                    'IVATasaMin': 10,
                    # A-C121 Total IVA Tasa Básica? Monto del IVA Tasa Minima
                    'MntIVATasaMin': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        return res

    def _uy_found_related_invoice(self):
        """ return the related/origin cfe of a given cfe """
        # next version review to merge this with l10n_ar_edi _found_related_invoice method
        self.ensure_one()
        if self.l10n_latam_document_type_id.internal_type == 'credit_note':
            return self.reversed_entry_id
        elif self.l10n_latam_document_type_id.internal_type == 'debit_note':
            return self.debit_origin_id
        else:
            return self.browse()

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


class AccountMoveLine(models.Model):

    _inherit = "account.move.line"

    def _l10n_uy_get_cfe_indfact(self):
        """ B4: Indicador de facturación (IndFact)', Dato enviado en CFE.
        Indica si el producto o servicio es exento, o a que tasa está gravado o si corresponde a un concepto no
        facturable """
        # TODO por ahora, esto esta solo funcionando para un impuesto de tipo iva por cada linea de factura, debemos
        # implementar el resto de los casos
        self.ensure_one()
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes(self.move_id.company_id)
        value = {
            tax_vat_exempt.id: 1,   # 1: Exento de IVA
            tax_vat_10.id: 2,       # 2: Gravado a Tasa Mínima
            tax_vat_22.id: 3,       # 3: Gravado a Tasa Básica

            # Another cases for future
            # 4: Gravado a Otra Tasa/IVA sobre fictos
            # 5: Entrega Gratuita. Por ejemplo docenas de trece
            # 6: Producto o servicio no facturable. No existe validación, excepto si A-C20= 1, B-C4=6 o 7.
            # 7: Producto o servicio no facturable negativo. . No existe validación, excepto si A-C20= 1, B-C4=6 o 7.
            # 8: Sólo para remitos: Ítem a rebajar en e-remitos y en e- remitos de exportación. En área de referencia se debe indicar el N° de remito que ajusta
            # 9: Sólo para resguardos: Ítem a anular en resguardos. En área de referencia se debe indicar el N° de resguardo que anular
            # 11: Impuesto percibido
            # 12: IVA en suspenso
            # 13: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un no contribuyente (valida que A-C60≠2)
            # 14: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un contribuyente IVA mínimo, Monotributo o Monotributo MIDES (valida que A-C60=2)
            # 15: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un contribuyente IMEBA (valida A-C60 = 2)
            # 16: Sólo para ítems vendidos por contribuyentes con obligación IVA mínimo, Monotributo o Monotributo MIDES. Si A-C10=3, no puede utilizar indicadores 1, 2, 3, 4, 11 ni 12
            # TODO parece que tenemos estos tipos de contribuyente: IVA mínimo, Monotributo o Monotributo MIDES ver si cargarlos en el patner asi como la afip responsibility
        }

        if self.move_id.is_expo_cfe():
            return 10  # Exportación y asimiladas

        return value.get(self.tax_ids.id)
