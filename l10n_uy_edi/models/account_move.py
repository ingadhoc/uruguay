# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from datetime import datetime
from . import ucfe_errors
import base64
from lxml import etree
from io import BytesIO
from odoo.tools import xml_utils
from odoo.modules.module import get_module_resource
import logging


_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    # CFE Status
    l10n_uy_cfe_dgi_state = fields.Selection([
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
    ], 'CFE DGI State', copy=False)  # EstadoEnDgiCfeRecibido
    l10n_uy_cfe_ufce_state = fields.Selection([
        ('not_sent', 'Not Sent yet'),
        ('sent', 'Sent and waiting DGI validation'),
        ('ask_for_status', 'Ask For Status'),
        ('accepted', 'Accepted'),
        ('post', 'Validated in DGI'),
        ('rejected', 'Rejected by DGI'),
        ('cancelled', 'Cancelled'),
        # TODO no segura aun si lo vamos a usar, veriticar tambien todos los estados arriba.
        # ('objected', 'Accepted With Objections'),
        # ('manual', 'Manual'),
    ], 'CFE DGI State', copy=False)

    l10n_uy_dgi_acceptation_status = fields.Selection([
        ('received', 'Received'),
        ('ack_sent', 'Acknowledge Sent'),
        ('claimed', 'Claimed'),
        ('accepted', 'Accepted'),
    ], string='CFE Accept status', copy=False, help="""The status of the CFE Acceptation
    * Received: the DTE was received by us for vendor bills, by our customers for customer invoices.
    * Acknowledge Sent: the Acknowledge has been sent to the vendor.
    * Claimed: the DTE was claimed by us for vendor bills, by our customers for customer invoices.
    * Accepted: the DTE was accepted by us for vendor bills, by our customers for customer invoices.
    """)
    l10n_uy_cfe_partner_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
    ], string='CFE Partner Status', copy=False, help="""
    Status of sending the CFE to the partner:
    - Not sent: the CFE has not been sent to the partner but it has sent to DGI.
    - Sent: The CFE has been sent to the partner.""")

    l10n_uy_document_number = fields.Char('Document Number', copy=False)
    l10n_uy_cfe_uuid = fields.Char(
        'Clave o UUID del CFE', help="Unique identification per CFE in UCFE. Currently is formed by the concatenation"
        " of model name + record id", copy=False)
    # TODO este numero debe ser maximo 36 caracteres máximo. esto debemos mejorarlo

    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")

    # TODO not sure if we needed ir
    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)

    # TODO review that this button is named this way in v12
    def button_cancel(self):
        for record in self.filtered(lambda x: x.company_id.country_id == self.env.ref('base.uy')):
            # The move cannot be modified once the CFE has been accepted by the DGI
            if record.l10n_uy_cfe_dgi_state == '00':
                raise UserError(_('This %s is accepted by DGI. It cannot be cancelled. '
                                  'Instead you should revert it.') % record.l10n_latam_document_type_id.name)
            # record.l10n_cl_dte_status = 'cancelled'
        return super().button_cancel()

    # Buttons

    # TODO 13.0 change method to post / 14.0 _post or action_post
    def action_invoice_open(self):
        """ After validate the invoices in odoo we send it to dgi via uruware """

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id == self.env.ref('base.uy') and
            # 13.0 account.move: x.is_invoice()
            x.type in ['out_invoice', 'out_refund'] and
            # TODO possible we are missing electronic documents here, review the
            int(x.journal_document_type_id.document_type_id.code) in [
                101, 102, 103, 111, 112, 113, 181, 182, 121, 122, 123, 124, 131, 132, 133, 141, 142, 143, 151, 152,
                153])

        no_validated = self.env['account.invoice']

        # Send invoices to DGI and get the return info
        for inv in uy_invoices:

            # If we are on testing environment and we don't have uruware configuration we validate only locally.
            # This is useful when duplicating the production database for training purpose or others
            if not inv.company_id._is_connection_info_complete(raise_exception=False):
                inv._dummy_dgi_validation()
                continue

            # TODO maybe this can be moved to outside the for loop
            client, auth, transport = inv.company_id._get_client(return_transport=True)
            inv._l10n_uy_dgi_post(client, auth, transport)
            if inv.l10n_uy_cfe_dgi_state != '00':
                no_validated += inv

        super(AccountInvoice, self - no_validated).action_invoice_open()

    # Main methods

    def _l10n_uy_get_data(self, msg_type, extra_req={}):
        self.ensure_one()
        id_req = 1
        # TODO I think this should be unique? see how we can generated it,  int, need to be assing using a
        # sequence in odoo?
        now = datetime.utcnow()
        data = {
            'Req': {'TipoMensaje': msg_type, 'CodComercio': self.company_id.l10n_uy_uruware_commerce_code,
                    'CodTerminal': self.company_id.l10n_uy_uruware_terminal_code, 'IdReq': id_req},
            'CodComercio': self.company_id.l10n_uy_uruware_commerce_code,
            'CodTerminal': self.company_id.l10n_uy_uruware_terminal_code,
            'RequestDate': now.replace(microsecond=0).isoformat(),
            'Tout': '30000',
        }
        if extra_req:
            data.get('Req').update(extra_req)
        return data

    # def _l10n_uy_get_certificate(self):
    #     """ This methos is to consult the Certificate and the Private Key to Sign the CFE documents """
    #     client, auth, transport = self.company_id._get_client(return_transport=True)
    #     # TODO Ver si realmente es necesario que guardemos el certificado en local, podemos extaerlo de la factura
    #     # alidada, pero por lo pronto no parece que lo necesitamos guardar en odoo.
    #     # certificate = self._l10n_uy_get_certificate()
    #     # certificate = base64.decodestring(inv.company_id.l10n_uy_dgi_crt).decode('ascii')

    #     # TODO no importa como lo usemos, siempre recibimos
    #     # Codigo Respuesta: 01 "Petición denegada"
    #     # Mensaje de Respuesta: Operación no autorizada'

    #     # 200 Solicitar Certificado
    #     data = self._l10n_uy_get_data('200')
    #     response = client.service.Invoke(data)
    #     print(" ---- 200 Solicitar Certificado: %s\n\n%s" % (ucfe_errors._hint_msg(response), response))

    #     # 210 Solicitar clave Certificado
    #     data = self._l10n_uy_get_data('210')
    #     response = client.service.Invoke(data)
    #     print(" ---- 210 Solicitar clave Certificado: %s\n\n%s" % (ucfe_errors._hint_msg(response), response))

    # def _l10n_uy_get_numeration(self):
    #     # TODO This method cna be delete if we have the certificate in UCFE, review if usefull for local sequences
    #     self.ensure_one()
    #     client, auth, transport = self.company_id._get_client(return_transport=True)

    #     # 220 Solicitud de rango de numeración
    #     now = datetime.utcnow()
    #     req_data = {
    #         'TipoCfe': int(self.journal_document_type_id.document_type_id.code),
    #         'FechaReq': now.date().strftime('%Y%m%d'),
    #     }
    #     data = self._l10n_uy_get_data('220', req_data)
    #     response = client.service.Invoke(data)
    #     print(response)

    #     # review 'Serie': None,
    #     raise UserError(ucfe_errors._hint_msg(response))

    def _l10n_uy_dgi_post(self, client, auth, transport):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """
        for inv in self:
            now = datetime.utcnow()
            CfeXmlOTexto = self._l10n_uy_create_cfe().get('cfe_str')  # TODO WIP make this properly work
            req_data = {
                'Uuid': 'account.invoice-' + str(self.id),  # TODO we need to set this unique how?
                'TipoCfe': int(inv.journal_document_type_id.document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto,
            }
            data = inv._l10n_uy_get_data('310', req_data)
            response = client.service.Invoke(data)
            self.message_post(body=ucfe_errors._hint_msg(response))

            self.l10n_uy_dgi_xml_request = CfeXmlOTexto
            self.l10n_uy_dgi_xml_response = transport.xml_response
            self.l10n_uy_cfe_dgi_state = response.Resp.EstadoEnDgiCfeRecibido
            self.l10n_uy_cfe_uuid = response.Resp.Uuid

            if response.Resp.CodRta != '00':
                return

            # If everything is ok we save the return information
            self.l10n_uy_document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)
            self.l10n_uy_cfe_dgi_state = response.Resp.EstadoEnDgiCfeRecibido

            # TODO este viene vacio, ver cuando realmente es seteado para asi setearlo en este momento
            # Tambien tenemos ver para que sirve 'DatosQr': 'https://www.efactura.dgi.gub.uy/consultaQRPrueba/cfe?218435730016,101,A,1,18.00,17/09/2020,gKSy8dDHR0YsTy0P4cx%2bcSu4Zvo%3d',
            # self.l10n_uy_dgi_barcode = response.Resp.ImagenQr

            # TODO evaluate if this is usefull to put it in a invoice place?
            # 'Adenda': None,
            # 'CodRta': '00',
            # 'CodigoSeguridad': 'gKSy8d',
            # 'EstadoSituacion': None,
            # 'Etiquetas': None,
            # 'FechaFirma': '2020-09-17T19:50:50.0000000-03:00',
            # 'FechaReq': None,
            # 'HoraReq': None,
            # 'IdCae': '90200001010',
            # 'IdReq': '1',
            # 'MensajeRta': None,
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

    # Consulta si un RUT es emisor electrónico 630 / 631
    # RUT consultado a DGI (función 640 – Consulta a DGI por datos de RUT)

    # simil to _l10n_mx_edi_create_cfdi_values
    def _l10n_ar_edi_create_xml_values(self):
        '''Create the values to fill the xml.'''
        self.ensure_one()
        precision_digits = self.currency_id.l10n_mx_edi_decimal_places
        if precision_digits is False:
            raise UserError(_(
                "The SAT does not provide information for the currency %s.\n"
                "You must get manually a key from the PAC to confirm the "
                "currency rate is accurate enough."), self.currency_id)
        partner_id = self.partner_id
        if self.partner_id.type != 'invoice':
            partner_id = self.partner_id.commercial_partner_id
        values = {
            'record': self,
            'currency_name': self.currency_id.name,
            'supplier': self.company_id.partner_id.commercial_partner_id,
            'issued': self.journal_id.l10n_mx_address_issued_id,
            'customer': partner_id,
            'fiscal_regime': self.company_id.l10n_mx_edi_fiscal_regime,
            'payment_method': self.l10n_mx_edi_payment_method_id.code,
            'use_cfdi': self.l10n_mx_edi_usage,
            'conditions': self._get_string_cfdi(
                self.invoice_payment_term_id.name, 1000) if self.invoice_payment_term_id else False,
        }

        values.update(self._l10n_mx_get_serie_and_folio(self.name))
        ctx = dict(company_id=self.company_id.id, date=self.invoice_date)
        mxn = self.env.ref('base.MXN').with_context(ctx)
        invoice_currency = self.currency_id.with_context(ctx)
        values['rate'] = ('%.6f' % (
            invoice_currency._convert(1, mxn, self.company_id, self.invoice_date or fields.Date.today(), round=False))) if self.currency_id.name != 'MXN' else False

        values['document_type'] = 'ingreso' if self.type == 'out_invoice' else 'egreso'
        values['payment_policy'] = self._l10n_mx_edi_get_payment_policy()
        domicile = self.journal_id.l10n_mx_address_issued_id or self.company_id
        values['domicile'] = '%s %s, %s' % (
                domicile.city,
                domicile.state_id.name,
                domicile.country_id.name,
        )

        values['decimal_precision'] = precision_digits
        subtotal_wo_discount = lambda l: float_round(
            l.price_subtotal / (1 - l.discount/100) if l.discount != 100 else
            l.price_unit * l.quantity, int(precision_digits))
        values['subtotal_wo_discount'] = subtotal_wo_discount
        get_discount = lambda l, d: ('%.*f' % (
            int(d), subtotal_wo_discount(l) - l.price_subtotal)) if l.discount else False
        values['total_discount'] = get_discount
        total_discount = sum([float(get_discount(p, precision_digits)) for p in self.invoice_line_ids])
        values['amount_untaxed'] = '%.*f' % (
            precision_digits, sum([subtotal_wo_discount(p) for p in self.invoice_line_ids]))
        values['amount_discount'] = '%.*f' % (precision_digits, total_discount) if total_discount else None

        values['taxes'] = self._l10n_mx_edi_create_taxes_cfdi_values()
        values['amount_total'] = '%0.*f' % (precision_digits,
            float(values['amount_untaxed']) - float(values['amount_discount'] or 0) + (
                values['taxes']['total_transferred'] or 0) - (values['taxes']['total_withhold'] or 0))

        values['tax_name'] = lambda t: {'ISR': '001', 'IVA': '002', 'IEPS': '003'}.get(t, False)

        if self.l10n_mx_edi_partner_bank_id:
            digits = [s for s in self.l10n_mx_edi_partner_bank_id.acc_number if s.isdigit()]
            acc_4number = ''.join(digits)[-4:]
            values['account_4num'] = acc_4number if len(acc_4number) == 4 else None
        else:
            values['account_4num'] = None

        values.update(self._get_external_trade_values(values))
        return values

    def _l10n_uy_get_invoice_line_item_detail(self):
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

    def _l10n_uy_create_cfe(self):
        """ Create the CFE xml estructure
        :return: A dictionary with one of the following key:
            * cfe_str: A string of the unsigned cfe.
            * error: An error if the cefe was not successfuly generated. """
        # TODO wip
        self.ensure_one()

        now = datetime.utcnow()  # TODO this need to be the same as the tipo de mensaje?
        cfe = self.env.ref('l10n_uy_edi.cfe_template').render({
            'move': self,
            'FchEmis': now.date().strftime('%Y-%m-%d'),
            'item_detail': self._l10n_uy_get_invoice_line_item_detail(),
            'totals_detail': self._l10n_uy_get_invoice_line_totals_detail(),
            # 'get_cl_current_strftime': self._get_cl_current_strftime,
            # 'format_length': self._format_length,
        })

        from html import unescape
        cfe = unescape(cfe.decode('utf-8')).replace(r'&', '&amp;')
        cfe_attachment = self.env['ir.attachment'].create({
            'name': 'CFE_{}.xml'.format(self.name),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'datas': base64.b64encode(cfe.encode('ISO-8859-1'))
        })
        self.l10n_uy_cfe_file = cfe_attachment.id

        # Check using the XSD
        # TODO do the validation here, using the xsd or the api
        # xsd_file_path = get_module_resource('l10n_uy_edi', 'data', 'CFEType.xsd')
        # file_content = open(xsd_file_path, 'rb').read()
        # xsd_datas = base64.b64decode(file_content)  # TODO I think this is not neccesary, test it
        # if xsd_datas:
        # try:
        #     # xml_utils._check_with_xsd(cfe, xsd)
        #     return xml_utils._check_with_xsd(cfe, xsd_fname, self.env)
        # except FileNotFoundError:
        #     _logger.info(_('The XSD validation files from DGI has not been found, please run manually the cron: "Download XSD"'))
        # except Exception as e:
        #     return {'errors': str(e).split('\\n')}

        return {
            # 'cfe_str': etree.tostring(cfe, pretty_print=True, xml_declaration=True, encoding='UTF-8'),
            'cfe_str': cfe,
        }

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

    def _l10n_uy_get_invoice_line_totals_detail(self):
        self.ensure_one()
        res = {}
        res.update({
            'TpoMoneda': self._l10n_uy_get_currency(),  # A-C110 Tipo moneda transacción
            'MntNetoIVATasaBasica': 14.75,  # A-C116 Total Monto Neto - IVA Tasa Minima TODO
            'IVATasaMin': 10,  # A119 Tasa Mínima IVA TODO
            'IVATasaBasica': 22,  # A120 Tasa Mínima IVA TODO
            'MntIVATasaBasica': 3.25,  # A-C122 Total IVA Tasa Básica? Monto del IVA Tasa Basica TODO
            'MntTotal': self.amount_total,  # TODO A-C124? Total Monto Total SUM(A121:A123)
            'CantLinDet': len(self.invoice_line_ids),  # A-C126 Lineas
            'MntPagar': self.amount_total,  # A-C130 Monto Total a Pagar
            # TODO
            # <MntIVATasaBasica>3.25</MntIVATasaBasica>  importe impuesto
            # <MntNetoIVATasaBasica>14.75</MntNetoIVATasaBasica>  valor precio linea
            # <MntTotal>18.00</MntTotal>
        })
        return res


class AccountInvoiceLine(models.Model):

    _inherit = "account.invoice.line"

    def _l10n_uy_get_cfe_indfact(self):
        """ B4: Indicador de facturación (IndFact)', Dato enviado en CFE.
        Indica si el producto o servicio es exento, o a que tasa está gravado o si corresponde a un concepto no
        facturable """
        # TODO por ahora, esto esta solo funcionando para un impuesto de tipo iva por cada linea de factura, debemos
        # implementar el resto de los casos
        self.ensure_one()
        taxes = self.env['account.tax'].search([])
        tax_vat_exempt = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_exempt"))
        tax_vat_10 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_10"))
        tax_vat_22 = taxes.filtered(lambda x: x.tax_group_id == self.env.ref("l10n_uy.tax_group_vat_22"))
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
