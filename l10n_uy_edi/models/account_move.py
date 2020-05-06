# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import UserError, RedirectWarning
from odoo.tools.float_utils import float_repr, float_round
from datetime import datetime
from . import ucfe_errors
import logging


_logger = logging.getLogger(__name__)


class AccountMove(models.Model):

    _inherit = "account.move"

    l10n_uy_dgi_state = fields.Selection([('not', 'Not Sent yet'), ('sent', 'Sent and waiting DGI validation'), ('post', 'Validated in DGI'), ('rejected', 'Rejected by DGI')], 'DGI State')
    l10n_uy_document_number = fields.Char('Document Number', copy=False)
    l10n_uy_uuid = fields.Char('Uuid request to Uruware', copy=False)
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")

    # Buttons

    def post(self):
        """ After validate the invoice we then validate in AFIP. The last thing we do is request the cae because if an
        error occurs after CAE requested, the invoice has been already validated on AFIP """
        uy_invoices = self.filtered(lambda x: x.is_invoice() and x.company_id.country_id == self.env.ref('base.uy'))
        sale_uy_invoices = uy_invoices.filtered(lambda x: x.type in ['out_invoice', 'out_refund'])
        sale_uy_edi_invoices = sale_uy_invoices.filtered(lambda x: x.journal_id.l10n_ar_afip_ws)

        # TODO make it simpler, we do not need to have this syncronized I think

        # Send invoices to DGI and get the return info
        validated = error_invoice = self.env['account.move']
        for inv in sale_uy_edi_invoices:

            # If we are on testing environment and we don't have uruware configuration we validate only locally.
            # This is useful when duplicating the production database for training purpose or others
            if not inv.company_id._is_connection_info_complete():
                inv._dummy_dgi_validation()
                super(AccountMove, inv).post()
                validated += inv
                continue

            client, auth, transport = self.company_id._get_client(return_transport=True)
            super(AccountMove, inv).post()
            return_info = inv._l10n_uy_dgi_post(client, auth, transport)
            if return_info:
                error_invoice = inv
                break
            validated += inv

        if error_invoice:
            msg = _('We couldn\'t validate the invoice "%s" (Draft Invoice *%s) in DGI. This is what we get:\n%s') % (inv.partner_id.name, inv.id, return_info)
            # if we've already validate any invoice, we've commit and we want to inform which invoices were validated
            # which one were not and the detail of the error we get. This ins neccesary because is not usual to have a
            # raise with changes commited on databases
            if validated:
                unprocess = self - validated - error_invoice
                msg = _('Some invoices where validated in AFIP but as we have an error with one invoice the batch validation was stopped\n'
                        '\n* These invoices were validated:\n   * %s\n' % ('\n   * '.join(validated.mapped('name'))) +
                        '\n* These invoices weren\'t validated:\n%s\n' % ('\n'.join(['   * %s: "%s" amount %s' % (
                            item.display_name, item.partner_id.name, item.amount_total_signed) for item in unprocess])) + '\n\n\n' + msg)
            raise UserError(msg)

        return super(AccountMove, self - sale_uy_edi_invoices).post()

        # Consulta si un RUT es emisor electrónico 630 / 631
        """
        <web:req>
            <web:Req>
                <web:CfeXmlOTexto><![CDATA[
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

    # Main methods

    def _l10n_uy_dgi_post(self, client, auth, transport):
        # TODO improve
        client, _auth = self.company_id._get_client()
        data = {'Req': {'TipoMensaje': '210?','CodComercio': self.l10n_uy_uruware_commerce_code,
                        'CodTerminal': self.l10n_uy_uruware_terminal_code,
                        'FechaReq': fields.Date.today().strftime('%Y%m%d')}}
        response = client.service.Invoke(data)
        return response

    # Helpers

    def _dummy_dgi_validation(self):
        """ Only when we want to skip AFIP validation in testing environment. Fill the AFIP fields with dummy values in
        order to continue with the invoice validation without passing to AFIP validations
        """
        # TODO need to update to the result we need
        # self.write({'l10n_ar_afip_auth_mode': 'CAE',
        #             'l10n_ar_afip_auth_code': '68448767638166',
        #             'l10n_ar_afip_auth_code_due': self.invoice_date,
        #             'l10n_ar_afip_result': ''})
        # self.message_post(body=_('Invoice validated locally because it is in a testing environment without testing certificate/keys'))
