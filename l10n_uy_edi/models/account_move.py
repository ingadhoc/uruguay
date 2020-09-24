# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _, api
from odoo.exceptions import UserError
from . import ucfe_errors
from datetime import datetime
from html import unescape
import base64
import logging


_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    l10n_uy_cfe_dgi_state = fields.Selection([
        ('-2', 'No enviado, monto menor a 10.000 UI'),
        ('-1', 'Esperando Respuesta DGI'),
        ('00', 'aceptado por DGI'),
        ('05', 'rechazado por DGI'),
        ('06', 'observado por DGI'),
        ('11', 'UCFE no pudo consultar a DGI (puede intentar volver a ejecutar la consulta con la función 650 – Consulta a DGI por CFE recibido)'),
        ('10', 'aceptado por DGI pero no se pudo ejecutar la consulta QR'),
        ('15', 'rechazado por DGI pero no se pudo ejecutar la consulta QR'),
        ('16', 'observado por DGI pero no se pudo ejecutar la consulta QR'),
        ('20', 'aceptado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
        ('25', 'rechazado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
        ('26', 'observado por DGI pero la consulta QR indica que hay diferencias con el CFE recibido'),
    ], 'CFE DGI State', copy=False, readonly=True, track_visibility='onchange')  # EstadoEnDgiCfeRecibido

    l10n_uy_ufce_state = fields.Selection([
        ('00', 'Petición aceptada y procesada'),
        ('01', 'Petición denegada'),
        ('03', 'Comercio inválido'),
        ('05', 'CFE rechazado por DGI'),
        ('06', 'CFE observado por DGI'),
        ('11', 'CFE aceptado por UCFE, en espera de respuesta de DGI'),
        ('12', 'Requerimiento inválido'),
        ('30', 'Error en formato'),
        ('31', 'Error en formato de CFE'),
        ('89', 'Terminal inválida'),
        ('96', 'Error en sistema'),
        ('99', 'Sesión no iniciada'),
    ], 'UFCE State', copy=False, readonly=True, track_visibility='onchange')  # CodRta

    l10n_uy_ufce_msg = fields.Char('UFCE Mensaje de Respuesta', copy=False, readonly=True, track_visibility='onchange')  # MensajeRta

    l10n_uy_ufce_notif = fields.Selection([
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
        ], 'UFCE Tipo de Notificacion', copy=False, readonly=True, track_visibility='onchange')  # TipoNotificacion

    l10n_uy_cfe_uuid = fields.Char(
        'Clave o UUID del CFE', help="Unique identification per CFE in UCFE. Currently is formed by the concatenation"
        " of model name + record id", copy=False)
    # TODO este numero debe ser maximo 36 caracteres máximo. esto debemos mejorarlo

    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")

    # TODO integrate with l10n_ar_currency_rate in next versions
    # solo mostrar en estado draft?
    l10n_uy_currency_rate = fields.Float(copy=False, digits=(16, 4), string="Currency Rate")

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

    # Buttons

    def action_invoice_cancel(self):
        for record in self.filtered(lambda x: x.company_id.country_id == self.env.ref('base.uy')):
            # The move cannot be modified once has been sent to UCFE
            if record.l10n_uy_ufce_state in ['00', '05', '06', '11']:
                raise UserError(_('This %s has been already sent to UFCE. It cannot be cancelled. '
                                  'You can only click Consult DGI State to update.') % record.journal_document_type_id.document_type_id.name)
            # The move cannot be modified once the CFE has been accepted by the DGI
            elif record.l10n_uy_cfe_dgi_state == '00':
                raise UserError(_('This %s is accepted by DGI. It cannot be cancelled. '
                                  'Instead you should revert it.') % record.journal_document_type_id.document_type_id.name)
            # record.l10n_cl_dte_status = 'cancelled'
        return super().action_invoice_cancel()

    # TODO 13.0 change method to post / 14.0 _post or action_post
    def action_invoice_open(self):
        """ After validate the invoices in odoo we send it to dgi via ucfe """

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id == self.env.ref('base.uy') and
            # 13.0 account.move: x.is_invoice()
            x.type in ['out_invoice', 'out_refund'] and
            x.l10n_uy_ufce_state not in ['00', '05', '06', '11'] and # Already sent and waiting status from UFCE
            # TODO possible we are missing electronic documents here, review the
            int(x.journal_document_type_id.document_type_id.code) > 100)

        no_validated = self.env['account.invoice']

        # Send invoices to DGI and get the return info
        for inv in uy_invoices:

            # If we are on testing environment and we don't have ucfe configuration we validate only locally.
            # This is useful when duplicating the production database for training purpose or others
            if not inv.company_id._is_connection_info_complete(raise_exception=False):
                inv._dummy_dgi_validation()
                continue

            # TODO maybe this can be moved to outside the for loop
            client, auth, transport = inv.company_id._get_client(return_transport=True)
            inv._l10n_uy_dgi_post(client, auth, transport)
            if inv.l10n_uy_ufce_state not in ['00', '05', '06', '11']:
                no_validated += inv

        super(AccountInvoice, self - no_validated).action_invoice_open()

    def action_l10n_uy_get_dgi_state(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI, """
        self.ensure_one()
        client, auth = self.company_id._get_client()
        req_data = {
            'Uuid': self.l10n_uy_cfe_uuid,
        }
        data = self._l10n_uy_get_data('360', req_data)
        response = client.service.Invoke(data)

        ui_indexada = self._l10n_uy_get_unidad_indexada()
        self.l10n_uy_ufce_state = response.Resp.CodRta or self.l10n_uy_ufce_state
        self.l10n_uy_ufce_msg = response.Resp.MensajeRta or self.l10n_uy_ufce_msg
        self.l10n_uy_ufce_notif = response.Resp.TipoNotificacion or self.l10n_uy_ufce_notif
        self.l10n_uy_cfe_dgi_state = response.Resp.EstadoEnDgiCfeRecibido or \
                ('-2' if self.amount_total < ui_indexada else False) or \
                ('-1' if self.l10n_uy_ufce_state == '11' else False) or self.l10n_uy_cfe_dgi_state

    # Main methods

    def _l10n_uy_get_data(self, msg_type, extra_req={}):
        self.ensure_one()
        id_req = 1
        # TODO I think this should be unique? see how we can generated it,  int, need to be assing using a
        # sequence in odoo?
        now = datetime.utcnow()
        data = {
            'Req': {'TipoMensaje': msg_type, 'CodComercio': self.company_id.l10n_uy_ucfe_commerce_code,
                    'CodTerminal': self.company_id.l10n_uy_ucfe_terminal_code, 'IdReq': id_req},
            'CodComercio': self.company_id.l10n_uy_ucfe_commerce_code,
            'CodTerminal': self.company_id.l10n_uy_ucfe_terminal_code,
            'RequestDate': now.replace(microsecond=0).isoformat(),
            'Tout': '30000',
        }
        if extra_req:
            data.get('Req').update(extra_req)
        return data

    def _l10n_uy_dgi_post(self, client, auth, transport):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """
        for inv in self:
            now = datetime.utcnow()
            CfeXmlOTexto = self._l10n_uy_create_cfe().get('cfe_str')
            req_data = {
                'Uuid': 'account.invoice-' + str(self.id),  # TODO we need to set this unique how?
                'TipoCfe': int(inv.journal_document_type_id.document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto,
            }
            data = inv._l10n_uy_get_data('310', req_data)
            response = client.service.Invoke(data)

            ui_indexada = self._l10n_uy_get_unidad_indexada()
            self.l10n_uy_dgi_xml_request = CfeXmlOTexto
            # from lxml import etree
            # etree.tostring(etree.fromstring(response.Resp.XmlCfeFirmado), pretty_print=True).decode('utf-8')
            self.l10n_uy_dgi_xml_response = transport.xml_response
            self.l10n_uy_cfe_uuid = response.Resp.Uuid
            self.l10n_uy_ufce_state = response.Resp.CodRta

            self.l10n_uy_cfe_dgi_state = response.Resp.EstadoEnDgiCfeRecibido or \
                ('-2' if self.amount_total < ui_indexada else False) or \
                ('-1' if self.l10n_uy_ufce_state == '11' else False)

            self.l10n_uy_ufce_msg = response.Resp.MensajeRta
            self.l10n_uy_ufce_notif = response.Resp.TipoNotificacion

            self.l10n_ar_currency_rate = getattr(response.Resp, 'TpoCambio', 0)

            if response.Resp.CodRta not in ['00', '05', '06', '11']:
                return

            # If everything is ok we save the return information
            self.document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)

            # TODO this one is failing, review why
            self.l10n_uy_cfe_file = self.env['ir.attachment'].create({
                'name': 'CFE_{}.xml'.format(self.document_number), 'res_model': self._name, 'res_id': self.id,
                'type': 'binary', 'datas': base64.b64encode(CfeXmlOTexto.encode('ISO-8859-1'))}).id

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

            # ??? – Recepcion de CFE en UFCE
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
        if self.document_type_id.code in [101, 102, 103, 131, 132, 133] and len(self.invoice_line_ids) > 700:
            raise UserError('Para e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección solo puede'
                            ' reportar Hasta 700')
        # Otros CFE: Hasta 200
        elif len(self.invoice_line_ids) > 200:
            raise UserError('Para este tipo de CFE solo puede reportar hasta 200 lineas')

        for k, line in enumerate(self.invoice_line_ids, 1):
            res.append({
                'NroLinDet': k,  # B1 No de línea o No Secuencial. a partir de 1
                'IndFact': line._l10n_uy_get_cfe_indfact(),  # B4 Indicador de facturación
                'NomItem': line.name[:80],  # B7 Nombre del ítem (producto o servicio). Maximo 80 caracteres

                'Cantidad': line.quantity,  # B9 Cantidad. NUM 17
                # TODO OJO se admite negativo? desglozar
                # TODO Valor numerico 14 enteros y 3 decimales. debemos convertir el formato a representarlo

                'UniMed': line.uom_id.name[:4] if line.uom_id else 'N/A',  # B10 Unidad de medida
                'PrecioUnitario': line.price_total,  # B11 Precio unitario
                'MontoItem': line.price_total,  # B24 Monto Item,
            })
        return res

    @api.model
    def _l10n_uy_get_unidad_indexada(self):
        # TODO averiguar si realmente esta es la unidad indexada
        return 4.6988 * 10000

    def _l10n_uy_get_cfe_receptor(self):
        self.ensure_one()
        res = {}
        ui_indexada = self._l10n_uy_get_unidad_indexada()
        document_type = int(self.journal_document_type_id.document_type_id.code)
        cond_e_fact = document_type in [111, 112, 113, 141, 142, 143]
        cond_e_ticket = document_type in [101, 102, 103, 131, 132, 133] and self.amount_total > ui_indexada
        cond_e_boleta = document_type in [151, 152, 153]

        if cond_e_fact or cond_e_ticket or cond_e_boleta:
            # cond_e_fact: obligatorio RUC (C60= 2).
            # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E), debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).

            tipo_doc = self.partner_id.main_id_category_id.l10n_uy_dgi_code
            cod_pais = 'UY' if tipo_doc in [2, 3] else '99'

            res.update({
                # TODO -Free Shop: siempre se debe identificar al receptor.
                'TipoDocRecep': tipo_doc,  # C60
                'CodPaisRecep': self.partner_id.country_id.code or cod_pais,   # C61
                'DocRecep' if tipo_doc in [1, 2, 3] else 'DocRecepExt': self.partner_id.main_id_number,  # C62 / C62.1
        })
        return res

    def _l10n_uy_get_cfe_tag(self):
        self.ensure_one()
        cfe_code = int(self.journal_document_type_id.document_type_id.code)
        if cfe_code in [101, 102, 103, 201]:
            return 'eTck'
        elif cfe_code in [111, 112]:
            return 'eFact'
        elif cfe_code in [121, 122]:
            return 'eFact_Exp'
        else:
            raise UserError('Este Comprobante aun no ha sido implementado')

    def _l10n_uy_get_cfe_referencia(self):
        res = {}
        # If is a debit/credit note cfe then we need to inform el tag referencia
        if self.journal_document_type_id.document_type_id.internal_type in ['credit_note', 'debit_note']:
            for k, related_cfe in enumerate(self._l10n_uy_get_related_invoices_data(), 1):
                res.update({
                    'NroLinRef': k,
                })
        return res

    def _l10n_uy_create_cfe(self):
        """ Create the CFE xml estructure and validate it
            :return: A dictionary with one of the following key:
            * cfe_str: A string of the unsigned cfe.
            * error: An error if the cfe was not successfully generated. """

        self.ensure_one()
        now = datetime.utcnow()  # TODO this need to be the same as the tipo de mensaje?
        cfe = self.env.ref('l10n_uy_edi.cfe_template').render({
            'move': self,
            'FchEmis': now.date().strftime('%Y-%m-%d'),
            'item_detail': self._l10n_uy_get_cfe_item_detail(),
            'totals_detail': self._l10n_uy_get_cfe_totals(),
            'receptor': self._l10n_uy_get_cfe_receptor(),
            'cfe_tag': self._l10n_uy_get_cfe_tag(),
            'referencia': self._l10n_uy_get_cfe_referencia(),
        })
        cfe = unescape(cfe.decode('utf-8')).replace(r'&', '&amp;')

        # Check CFE XML valid files
        # 350: Validación de estructura de CFE
        client, _auth = self.company_id._get_client()
        data = self._l10n_uy_get_data('350', {'CfeXmlOTexto': cfe})
        response = client.service.Invoke(data)
        # import pdb; pdb.set_trace()

        if response.Resp.CodRta != '00':
            # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
            # response.Resp.MensajeRta
            raise UserError('Error al crear el XML del CFẸ\n\n' + cfe + '\n\n' + ucfe_errors._hint_msg(response))
            # return {'errors': str(e).split('\\n')}s
        return {'cfe_str': cfe}

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
            'IVATasaMin': 10,  # A119 Tasa Mínima IVA TODO
            'IVATasaBasica': 22,  # A120 Tasa Mínima IVA TODO
            'MntTotal': self.amount_total,  # TODO A-C124? Total Monto Total SUM(A121:A123)
            'CantLinDet': len(self.invoice_line_ids),  # A-C126 Lineas
            'MntPagar': self.amount_total,  # A-C130 Monto Total a Pagar
        })

        # C111 Tipo de Cambio
        if self._l10n_uy_get_currency() != 'UYU':
            res['TpoCambio'] = '{:.3f}'.format(self.currency_id._convert(
                1.0, self.company_id.currency_id, self.company_id, self.date_invoice or fields.Date.today(),
                round=False))

        # TODO this need to be improved, using a different way to print the tax information
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes()

        tax_line_basica = self.tax_line_ids.filtered(lambda x: x.tax_id == tax_vat_22)
        if tax_line_basica:
            res.update({
                'MntNetoIVATasaBasica': '{:.2f}'.format(tax_line_basica.base),  # A-C117 Total Monto Neto - IVA Tasa Basica
                'MntIVATasaBasica': '{:.2f}'.format(tax_line_basica.amount_total),  # A-C122 Total IVA Tasa Básica? Monto del IVA Tasa Basica
            })

        tax_line_minima = self.tax_line_ids.filtered(lambda x: x.tax_id == tax_vat_10)
        if tax_line_basica:
            res.update({
                'MntNetoIVATasaMin': '{:.2f}'.format(tax_line_minima.base),  # A-C116 Total Monto Neto - IVA Tasa Minima
                'MntIVATasaMin': '{:.2f}'.format(tax_line_minima.amount_total),  # A-C121 Total IVA Tasa Básica? Monto del IVA Tasa Minima
            })

        return res

    @api.model
    def _get_available_journal_document_types(self, journal, invoice_type, partner):
        """ This function filter the journal documents types taking the type of journal"""
        res = super()._get_available_journal_document_types(journal, invoice_type, partner)
        if journal.localization == 'uruguay':
            domain = [('journal_id', '=', journal.id)]

            if invoice_type in ['out_refund', 'in_refund']:
                domain += [('document_type_id.internal_type', '=', 'credit_note')]
            else:
                domain += [('document_type_id.internal_type', 'not in', ['credit_note'])]

            journal_document_types = self.env['account.journal.document.type'].search(domain)

            if journal.l10n_uy_type == 'preprinted':
                available_types = [000]
            elif journal.l10n_uy_type == 'electronic':
                available_types = [101, 102, 103, 111, 112, 113, 121, 122, 123, 141, 142, 143, 201, 211, 212, 213, 221, 222, 223, 241, 242, 243]
            else:
                res['available_journal_document_types'] = False
                res['journal_document_type'] = False

            if available_types:
                res['available_journal_document_types'] = journal_document_types.filtered(
                    lambda x: int(x.document_type_id.code) in available_types)
                res['journal_document_type'] = res['available_journal_document_types'] and \
                    res['available_journal_document_types'][0]
        return res

    @api.multi
    def _l10n_uy_get_related_invoices_data(self):
        """ return the related/origin cfe of a given cfe """
        # similar to get_related_invoices_data from l10n_ar_afipws_fe, we need to remove
        # TODO when changing to 13.0 need to change this to something like _found_related_invoice() method
        self.ensure_one()
        if self.document_type_internal_type in ['debit_note', 'credit_note'] and self.origin:
            return self.search([
                ('commercial_partner_id', '=', self.commercial_partner_id.id),
                ('company_id', '=', self.company_id.id),
                ('document_number', '=', self.origin),
                ('id', '!=', self.id),
                ('document_type_id', '!=', self.document_type_id.id),
                ('document_type_id.localization', '=', self.localization),
                ('state', 'not in', ['draft', 'cancel'])],
                limit=1)
        else:
            return self.browse()


class AccountInvoiceLine(models.Model):

    _inherit = "account.invoice.line"

    def _l10n_uy_get_cfe_indfact(self):
        """ B4: Indicador de facturación (IndFact)', Dato enviado en CFE.
        Indica si el producto o servicio es exento, o a que tasa está gravado o si corresponde a un concepto no
        facturable """
        # TODO por ahora, esto esta solo funcionando para un impuesto de tipo iva por cada linea de factura, debemos
        # implementar el resto de los casos
        self.ensure_one()
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes()
        value = {
            tax_vat_exempt.id: 1,   # 1: Exento de IVA
            tax_vat_10.id: 2,       # 2: Gravado a Tasa Mínima
            tax_vat_22.id: 3,       # 3: Gravado a Tasa Básica

            # TODO implement this cases
            # 4: Gravado a Otra Tasa/IVA sobre fictos
            # 5: Entrega Gratuita. Por ejemplo docenas de trece
            # 6: Producto o servicio no facturable. No existe validación, excepto si A-C20= 1, B-C4=6 o 7.
            # 7: Producto o servicio no facturable negativo. . No existe validación, excepto si A-C20= 1, B-C4=6 o 7.
            # 8: Sólo para remitos: Ítem a rebajar en e-remitos y en e- remitos de exportación. En área de referencia se debe indicar el N° de remito que ajusta
            # 9: Sólo para resguardos: Ítem a anular en resguardos. En área de referencia se debe indicar el N° de resguardo que anular
            # 10: Exportación y asimiladas
            # 11: Impuesto percibido
            # 12: IVA en suspenso
            # 13: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un no contribuyente (valida que A-C60≠2)
            # 14: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un contribuyente IVA mínimo, Monotributo o Monotributo MIDES (valida que A-C60=2)
            # 15: Sólo para e-Boleta de entrada y sus notas de corrección: Ítem vendido por un contribuyente IMEBA (valida A-C60 = 2)
            # 16: Sólo para ítems vendidos por contribuyentes con obligación IVA mínimo, Monotributo o Monotributo MIDES. Si A-C10=3, no puede utilizar indicadores 1, 2, 3, 4, 11 ni 12

            # TODO parece que tenemos estos tipos de contribuyente: IVA mínimo, Monotributo o Monotributo MIDES
        }
        return value.get(self.invoice_line_tax_ids.id)
