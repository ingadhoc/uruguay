# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools.float_utils import float_repr, float_round
from datetime import datetime
from . import ucfe_errors
import logging


_logger = logging.getLogger(__name__)


class AccountInvoice(models.Model):

    _inherit = "account.invoice"

    l10n_uy_dgi_state = fields.Selection([
        ('not_sent', 'Not Sent yet'),
        ('sent', 'Sent and waiting DGI validation'),
        ('post', 'Validated in DGI'),
        ('rejected', 'Rejected by DGI')
        # ('ask_for_status', 'Ask For Status'),
        # ('accepted', 'Accepted'),
        # ('objected', 'Accepted With Objections'),
        # ('cancelled', 'Cancelled'),
        # ('manual', 'Manual'),
    ], 'DGI State', copy=False)

    l10n_uy_document_number = fields.Char('Document Number', copy=False)
    l10n_uy_uuid = fields.Char('Uuid request to Uruware', copy=False)
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")

    # Buttons

    # TODO 13.0 post
    def action_invoice_open(self):
        """ After validate the invoices in odoo we send it to dgi via uruware """
        super().action_invoice_open()

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id == self.env.ref('base.uy') and
            # 13.0 account.move: x.is_invoice()
            x.type in ['out_invoice', 'out_refund'] and
            # TODO possible we are missing electronic documents here, review the
            int(x.journal_document_type_id.document_type_id.code) in [
                101, 102, 103, 111, 112, 113, 181, 182, 121, 122, 123, 124, 131, 132, 133, 141, 142, 143, 151, 152,
                153])

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

    # Main methods

    def _l10n_uy_dgi_post(self, client, auth, transport):
        """ Implementación via bandeja de entrada: web services """
        import pdb; pdb.set_trace()
        for inv in self:
            now = datetime.utcnow()

            # TODO 1: - 200 Solicitar Certificado
            # data = {
            #     'Req': {
            #         'TipoMensaje': '200',
            #         'IdReq': '200',
            #         'CodComercio': inv.company_id.l10n_uy_uruware_commerce_code,
            #         'CodTerminal': inv.company_id.l10n_uy_uruware_terminal_code,
            #     }
            #     'CodComercio': inv.company_id.l10n_uy_uruware_commerce_code,
            #     'CodTerminal': inv.company_id.l10n_uy_uruware_terminal_code,
            #     'RequestDate': now.replace(microsecond=0).isoformat(),
            #     'Tout': '30000',
            # }
            # response = client.service.Invoke(data)
            # import pdb; pdb.set_trace()
            # CodRta, Mensaje Descriptivo Respuesta, Certificado para firmar CFE
            # COdigo 201

            # TODO 1: - 210 Solicitar Certificado

            # 2: 310 – Solicitud de firma de CFE
            # Envia datos xml, formato definido por DGI
            # TODO revisar la sección 6.2 – Formato XML.
            CfeXmlOTexto = """
                <CFE xmlns="http://cfe.dgi.gub.uy" version="1.0">
                <eTck>
                    <Encabezado>
                        <IdDoc>
                            <TipoCFE>101</TipoCFE>
                            <FchEmis>2020-06-02</FchEmis>
                            <MntBruto>1</MntBruto>
                            <FmaPago>1</FmaPago>
                        </IdDoc>
                        <Emisor>
                            <RUCEmisor>218435730016</RUCEmisor>
                            <RznSoc>BID Uruguayy</RznSoc>
                            <NomComercial>BID Empresas</NomComercial>
                            <EmiSucursal>Central</EmiSucursal>
                            <CdgDGISucur>4</CdgDGISucur>
                            <DomFiscal>Bv. España 2579</DomFiscal>
                            <Ciudad>Montevideo</Ciudad>
                            <Departamento>Montevideo</Departamento>
                        </Emisor>
                        <Totales>
                            <TpoMoneda>UYU</TpoMoneda>
                            <MntNetoIVATasaBasica>14.75</MntNetoIVATasaBasica>
                            <IVATasaMin>10</IVATasaMin>
                            <IVATasaBasica>22</IVATasaBasica>
                            <MntIVATasaBasica>3.25</MntIVATasaBasica>
                            <MntTotal>18.00</MntTotal>
                            <CantLinDet>1</CantLinDet>
                            <MntPagar>18.00</MntPagar>
                        </Totales>
                    </Encabezado>
                    <Detalle>
                        <Item>
                            <NroLinDet>1</NroLinDet>
                            <IndFact>3</IndFact>
                            <NomItem>PANESTENO</NomItem>
                            <Cantidad>1.000</Cantidad>
                            <UniMed>KILO</UniMed>
                            <PrecioUnitario>18.00</PrecioUnitario>
                            <MontoItem>18.00</MontoItem>
                        </Item>
                    </Detalle>
                </eTck>
                </CFE>
            """

            # import xml.etree.cElementTree as e
            # root = e.Element("CFE xmlns='http://cfe.dgi.gub.uy' version='1.0'")
            # document_type = e.SubElement(root, "eTck")
            # encabezado = e.SubElement(document_type, "Encabezado")

            # iddoc = e.SubElement(encabezado, "IdDoc")
            # e.SubElement(iddoc, "TipoCFE").text = 101
            # e.SubElement(iddoc, "FchEmis").text = '2020-06-02'
            # e.SubElement(iddoc, "MntBruto").text = 1
            # e.SubElement(iddoc, "FmaPago").text = 1

            # emisor = e.SubElement(encabezado, "Emisor")
            # e.SubElement(emisor, "RUCEmisor").text = 218435730016
            # e.SubElement(emisor, "RznSoc").text = 'BID Uruguayy'
            # e.SubElement(emisor, "NomComercial").text = 'BID Empresas'
            # e.SubElement(emisor, "NomComercial").text = 'BID Empresas'
            # a = e.ElementTree(root)

            data = {
                'CodComercio': inv.company_id.l10n_uy_uruware_commerce_code,
                'CodTerminal': inv.company_id.l10n_uy_uruware_terminal_code,
                'RequestDate': now.replace(microsecond=0).isoformat(),
                'Tout': '30000',
                'Req': {
                    'TipoMensaje': '310',
                    'TipoCfe': int(inv.journal_document_type_id.document_type_id.code),
                    'Uuid': 'clave_uuid',
                    'IdReq': 1,  # TODO int, need to be assing using a sequence in odoo?
                    'HoraReq': now.strftime('%H%M%S'),
                    'FechaReq': now.date().strftime('%Y%m%d'),

                    # Opcionales M2
                    'CodComercio': inv.company_id.l10n_uy_uruware_commerce_code,
                    'CodTerminal': inv.company_id.l10n_uy_uruware_terminal_code,
                    'CfeXmlOTexto': CfeXmlOTexto,
                }
            }
            response = client.service.Invoke(data)
            import pdb; pdb.set_trace()
            # <MensajeRta>No se ha encontrado un certificado válido.</MensajeRta>


        # <MensajeRta>No se ha encontrado un certificado válido.</MensajeRta>
        # Contiene el certificado X.509 versión 3 (1997) sin clave privada codificado en base64 (mismo dato que se agrega en los cabezales de los sobres). UCFE lo utiliza para validar la firma.
        # 200 / 201 - Solicitud de certificado
        # 210 / 211 - Solicitud de clave de certificado

        # UCFE debe recibir los comprobantes para su validación, firma y envío a DGI, así
        # como para informar al sistema los datos necesarios para la correcta emisión, por ejemplo, serie,
        # número, código QR, código de seguridad, etc.

        # TODO Esto es comprobante por comprobante, no acepta lotes, para lotes son otros codigo 340 y 330. Investigar porque hasta donde tengo entendido esto no funciona via webservice

        # ??? – Recepcion de CFE en UFCE
        # ??? – Conversion y validation



        # TODO comprobar. este devolvera un campo clave llamado UUID que permite identificar el comprobante, si es enviando dos vence sno genera otro CFE firmado

        # 300 – Envío de CFE firmado.

        """
        <CFE xmlns="http://cfe.dgi.gub.uy" version="1.0">
        <eTck>
        <Encabezado>
            <IdDoc>
                'TipoCFE': '101',
                'FchEmis': '2015-01-01',
                'MntBruto': 1,
                'FmaPago':1,
            </IdDoc>
            <Emisor>
                'RUCEmisor': '215521750017',
                'RznSoc': 'ZabaletaAsociadosSRL',
                'NomComercial': 'Uruware',
                'EmiSucursal': 'Central',
                'CdgDGISucur': '4',
                'DomFiscal': 'Bv',
                'Ciudad': 'Montevideo',
                'Departamento': 'Montevideo',
            </Emisor>
            <Totales>
                'TpoMoneda': 'UYU',
                'MntNetoIVATasaBasica': '14',
                'IVATasaMin': '10',
                'IVATasaBasica': '22',
                'MntIVATasaBasica': '3',
                'MntTotal': '18',
                'CantLinDet': '1',
                'MntPagar': '18',
            </Totales>
            </Encabezado>
        <Detalle>
            <Item>
                'NroLinDet': '1',
                'IndFact': '3',
                'NomItem': 'PANESTENO',
                'Cantidad': '1.000',
                'UniMed': 'KILO',
                'PrecioUnitario': '18.00',
                'MontoItem': '18.00',
            </Item>
        </Detalle>
        </eTck>
        </CFE>
        ]]>                   </web:CfeXmlOTexto>
                            'CodComercio': 'TEST01',
                            'CodTerminal': 'FCTEST01',
                            'FechaReq': '20150101',
                            'HoraReq': '120000',
                            'IdReq': '1',
                            'TipoCfe': '101',
                            'TipoMensaje': '310',
                            'Uuid': 'clave_uuid',
                        </web:Req>
                        'RequestDate': '2015-01-01T12:00:00',
                        'Tout': '30000',
                        'CodComercio': 'TEST01',
                        'CodTerminal': 'FCTEST01',
                    </web:req>
        """
        return response

    # Helpers

    def _dummy_dgi_validation(self):
        """ Only when we want to skip DGI validation in testing environment. Fill the DGI result  fields with dummy
        values in order to continue with the invoice validation without passing to DGI validations s"""
        # TODO need to update to the result we need, all the fields we need to add are not defined yet 
        self.write({
            'l10n_uy_uuid': '123456',
        })
        self.message_post(body=_('Validated locally because is not Uruware parameters are not properly configured'))


    # Consulta si un RUT es emisor electrónico 630 / 631
    # RUT consultado a DGI (función 640 – Consulta a DGI por datos de RUT)
