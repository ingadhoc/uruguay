# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime
import logging
import base64
import stdnum.uy
import re

from odoo import _, fields, models, api
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.float_utils import float_repr
from odoo.tools import format_amount, safe_eval, html2plaintext
from . import ucfe_errors


_logger = logging.getLogger(__name__)


class L10nUyCfe(models.AbstractModel):

    _name = 'l10n.uy.cfe'
    _description = 'Comprobante Fiscal Electrónico (UY)'

    # TODO KZ not sure if we needed
    # company_id = fields.Many2one("res.compaany")

    # Campos estados

    l10n_uy_cfe_state = fields.Selection([
        ('not_apply', 'Not apply - Not a CFE'),
        ('draft_cfe', 'Draft CFE'),

        # DGI states
        ('received', 'Waiting response from DGI'),
        ('accepted', 'CFE Accepted by DGI'),
        ('rejected', 'CFE Rejected by DGI'),

        # UCFE error states
        ('xml_error', 'ERROR: CFE XML not valid'),
        ('connection_error', 'ERROR: Connection to UCFE'),
        ('ucfe_error', 'ERROR: Related to UCFE'),
        ],
        string='CFE Status', copy=False, readonly=True, tracking=True,
        help="If 'ERROR: Related to UCFE' please check details of 'UCFE State'")

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
    ], 'DGI State', copy=False, readonly=True, tracking=True)  # EstadoEnDgiCfeRecibido

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
    ], 'UCFE State', copy=False, readonly=True, tracking=True)  # CodRta

    l10n_uy_ucfe_msg = fields.Text(
        'UCFE Mensaje de Respuesta',
        copy=False,
        readonly=True,
        tracking=True)  # MensajeRta

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
        ],
        'UCFE Tipo de Notificacion', copy=False, readonly=True, tracking=True)  # TipoNotificacion

    # TODO not sure this fields are going to make it
    l10n_uy_cfe_partner_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
    ], string='CFE Partner Status', readonly=True, copy=False, help="""
    Status of sending the CFE to the partner:
    - Not sent: the CFE has not been sent to the partner but it has sent to DGI.
    - Sent: The CFE has been sent to the partner.""")

    # Campos preparacion y acuseo de recepcion/envio xml

    l10n_uy_cfe_xml = fields.Text('XML CFE', copy=False, groups="base.group_system")
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")

    # Campos resultados almacenamiento de comprobantes emitidos

    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)
    l10n_uy_cfe_pdf = fields.Many2one('ir.attachment', string='CFE PDF Representation', copy=False)

    # Campos identificacion del documento

    l10n_uy_dgi_barcode = fields.Text('DGI Barcode', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_cfe_uuid = fields.Char(
        'Clave o UUID del CFE', help="Unique identification per CFE in UCFE. Currently is formed by the concatenation"
        " of model name + record id", copy=False)
    # TODO este numero debe ser maximo 36 caracteres máximo. esto debemos mejorarlo

    # Campos compartidos usados desde factura/remitos
    l10n_uy_cfe_sale_mod = fields.Selection([
        ('1', 'Régimen General'),
        ('2', 'Consignación'),
        ('3', 'Precio Revisable'),
        ('4', 'Bienes propios a exclaves aduaneros'),
        ('90', 'Régimen general- exportación de servicios'),
        ('99', 'Otras transacciones'),
    ], 'Modalidad de Venta', help="Este campo debe enviarse cuando se reporta un CFE de tipo e-Facutra de Exportación o su e-Remito")
    l10n_uy_cfe_transport_route = fields.Selection([
        ('1', 'Marítimo'),
        ('2', 'Aéreo'),
        ('3', 'Terrestre'),
        ('8', 'N/A'),
        ('9', 'Otro'),
    ], 'Vía de Transporte', help="Este campo debe enviarse cuando se reporta un CFE de tipo e-Facutra de Exportación o su e-Remito")

    l10n_uy_place_of_delivery = fields.Char(
        "Lugar de entrega",
        size=100,
        help="Indicación de donde s entrega la mercadería o se presta el servicio (Dirección, Sucursal, Puerto, etc,)")

    l10n_uy_extra_info_cfe = fields.Char(
        "Info. adicional del CFE",
        size=150,
        help="Otra información relativa al receptor")

    l10n_uy_is_cfe = fields.Boolean(
        compute="_compute_l10n_uy_is_cfe",
        help="Campo tecnico para saber si es un comprobante electronico o no y usarlo en la vista para mostrar o requerir ciertos campos."
        " por los momentos lo estamos usando solo para remitos pero podemos extenderlo para otros modelos"
    )

    @api.depends('l10n_latam_document_type_id')
    def _compute_l10n_uy_is_cfe(self):
        cfes = self.filtered(lambda x: x.l10n_latam_document_type_id and int(x.l10n_latam_document_type_id.code) > 0)
        cfes.l10n_uy_is_cfe = True
        (self - cfes).l10n_uy_is_cfe = False

    @api.model
    def _uy_cfe_already_sent(self):
        """ CFE that have any of this ufce_status can not be sent again to ucfe because they can not be changed

        - 00: Petición aceptada y procesada
        - 05: CFE rechazado por DGI
        - 06: CFE observado por DGI
        - 11: CFE aceptado por UCFE, en espera de respuesta de DGI """
        return ['00', '05', '06', '11']

    def _is_dummy_dgi_validation(self):
        # If we are on testing environment and we don't have ucfe configuration we validate only locally.
        # This is useful when duplicating the production database for training purpose or others
        self.ensure_one()
        return self.company_id._uy_get_environment_type() == 'testing' and \
            not self.company_id.sudo()._is_connection_info_complete(raise_exception=False)

    def action_l10n_uy_get_uruware_cfe(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,

        Nos permite extraer la info del comprobante que fue emitido desde uruware
        y que no esta en Odoo para asi quede la info de numero de documento tipo
        de documento estado del comprobante.
        """
        uy_docs = self.env['l10n_latam.document.type'].search([('country_id.code', '=', 'UY')])
        for rec in self:
            if not rec.l10n_uy_cfe_uuid:
                raise UserError(_('Necesita definir "Clave o UUID del CFE" para poder continuar'))
            if rec.l10n_uy_cfe_state and 'error' in rec.l10n_uy_cfe_state:
                raise UserError(_('No se puede obtener la factura de un comprobante con error'))
            # TODO en este momento estamos usando este 360 porque es el que tenemos pero estamos esperando respuesta de
            # soporte uruware a ver como podemos extraer mas información y poder validarla.
            response = rec.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': rec.l10n_uy_cfe_uuid})
            rec.write({
                'l10n_latam_document_number': response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe),
                'l10n_latam_document_type_id': uy_docs.filtered(lambda x: x.code == response.Resp.TipoCfe).id,
                'l10n_uy_ucfe_state': response.Resp.CodRta,
                'l10n_uy_ucfe_msg': response.Resp.MensajeRta,
            })
            rec._update_l10n_uy_cfe_state()
            # TODO Improve add logic:
            # 1. add information to the cfe xml
            # 2. cfe another data
            # 3. validation that is the same CFE

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

    def _l10n_uy_vaidate_cfe(self, cfe, raise_exception=False):
        # Check CFE XML valid files: 350: Validación de estructura de CFE
        response = self.company_id._l10n_uy_ucfe_inbox_operation('350', {'CfeXmlOTexto': cfe})
        if response.Resp.CodRta != '00':
            # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
            # response.Resp.MensajeRta
            if raise_exception:
                raise UserError('Error al crear el XML del CFẸ\n\n' + ucfe_errors._hint_msg(response))
            # return {'errors': str(e).split('\\n')}

    def _update_l10n_uy_cfe_state(self):
        """ Update the CFE State show to the user depending of the information of the UFCE and DGI State return from
        third party service.

        * Customer CFE (l10n_uy_ucfe_state = CodRta)
        * Vendor CFE (l10n_uy_cfe_dgi_state = EstadoEnDgiCfeRecibido) this last one not implemented yet

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

    def _l10n_uy_get_cfe_receptor(self):
        self.ensure_one()
        res = {}
        receptor_required = True
        document_type = int(self.l10n_latam_document_type_id.code)
        cond_e_fact = document_type in [111, 112, 113, 141, 142, 143]
        cond_e_ticket = document_type in [101, 102, 103, 131, 132, 133]
        cond_e_fact_expo = self.is_expo_cfe()
        cond_e_remito = self._is_uy_remito_type_cfe()
        # cond_e_boleta = document_type in [151, 152, 153]
        # cond_e_contg = document_type in [201, 202, 203]
        # cond_e_resguardo = self._is_uy_resguardo()
        # cond_e_fact: obligatorio RUC (C60= 2).
        # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E),
        # debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).

        # # Si soy e-ticket y el monto es menor al monto minimo no es necesario validar y enviar la info del receptor, la
        # enviamos solo si la tenemos disponible.
        min_amount = self._l10n_uy_get_min_by_unidad_indexada()
        if cond_e_ticket and self._amount_total_company_currency() < min_amount:
            receptor_required = False

        # Si no tenemos la info del receptor neceario, pero en el envio de la info del receptor no es requerido directamente
        # no la enviamos
        if not self.partner_id.vat and not receptor_required:
            return res

        tipo_doc = int(self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code)
        cod_pais = 'UY' if tipo_doc in [2, 3] else '99'

        # Validaciones de tener todo los dato del receptor cuando este es requerido
        if receptor_required:
            if not self.partner_id.l10n_latam_identification_type_id and not self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code:
                raise UserError(_('The partner of the CFE need to have a Uruguayan Identification Type'))
            if tipo_doc == 0:
                raise UserError(_('Debe indicar un tipo de documento Uruguayo para poder facturar a este cliente'))

        if cond_e_fact_expo or cond_e_fact or (cond_e_ticket and receptor_required):
            if not all([self.partner_id.street, self.partner_id.city, self.partner_id.state_id, self.partner_id.country_id, self.partner_id.vat]):
                msg = _('Necesita completar los datos del receptor: dirección, ciudad, provincia, pais del receptor y número de identificación')
                if cond_e_ticket:
                    msg += _('\n\nNOTA: Esto es requerido ya que el e-Ticket supera el monto minimo.\nMonto minimo = 5.000 * Unidad Indexada Uruguaya (>%s)' % format_amount(self.env, min_amount, self.company_currency_id))
                raise UserError(msg)

        if cond_e_remito and not all([self.partner_id.street, self.partner_id.city]):
            raise UserError(_('Debe configurar al menos la dirección y ciudad del receptor para poder enviar este e-Remito'))

        # Si tenemos la info disponible del receptor la enviamos no importa el caso (asi lo hace uruware)
        res.update({
            # TODO -Free Shop: siempre se debe identificar al receptor.
            'TipoDocRecep': tipo_doc,  # A60
            'CodPaisRecep': self.partner_id.country_id.code or cod_pais,   # A61
            'DocRecep' if tipo_doc in [1, 2, 3] else 'DocRecepExt': self.partner_id.vat,  # A62 / A62.1
        })

        res.update({'RznSocRecep': self.partner_id.commercial_partner_id.name[:150]})  # A63
        res.update(self._uy_cfe_A64_DirRecep())
        res.update(self._uy_cfe_A65_CiudadRecep())
        res.update(self._uy_cfe_A66_DeptoRecep())
        res.update(self._uy_cfe_A66_1_PaisRecep())
        res.update(self._uy_cfe_A68_InfoAdicional())

        if not self._is_uy_resguardo():
            res.update(self._uy_cfe_A69_LugarDestEnt())
            res.update(self._uy_cfe_A70_CompraID())

        return res

    def _uy_cfe_A70_CompraID(self):
        """ Número que identifica la compra: número de pedido, número orden de compra etc. LEN(50)
        Opcional para todos los tipos de documentos """
        self.ensure_one()
        res = False
        if not self._is_uy_resguardo():
            if 'purchase_order_number' in self.env['account.move'].fields_get().keys():
                res = (self.purchase_order_number or '')[:50]
        return {'CompraID': res} if res else {}

    def _l10n_uy_get_cfe_emisor(self):
        self.ensure_one()
        res = {}

        res.update(self._uy_cfe_A40_RUCEmisor())
        res.update(self._uy_cfe_A41_RznSoc())
        res.update(self._uy_cfe_A47_CdgDGISucur())
        res.update(self._uy_cfe_A48_DomFiscal())
        res.update(self._uy_cfe_A49_Ciudad())
        res.update(self._uy_cfe_A50_Departamento())
        return res

    def _uy_cfe_A40_RUCEmisor(self):
        self.ensure_one()
        if not self.company_id.partner_id._is_rut():
            raise UserError(_('Debe configurar el RUT emisor para poder emitir este documento (RUC en la compañia)'))
        res = stdnum.uy.rut.compact(self.company_id.vat)
        return {'RUCEmisor': res} if res else {}

    def _uy_cfe_A41_RznSoc(self):
        # TODO KZ company register name?
        self.ensure_one()
        res = self.company_id.name[:150]
        return {'RznSoc': res} if res else {}

    def _uy_cfe_A47_CdgDGISucur(self):
        self.ensure_one()
        res = self.company_id.l10n_uy_dgi_house_code
        return {'CdgDGISucur': res} if res else {}

    def _uy_cfe_A48_DomFiscal(self):
        self.ensure_one()
        res = ''
        if self.company_id.street:
            res += self.company_id.street
        if self.company_id.street2:
            res += ' ' + self.company_id.street2
        res = res[:70]
        return {'DomFiscal': res} if res else {}

    def _uy_cfe_A49_Ciudad(self):
        self.ensure_one()
        res = self.company_id.city[:30]
        return {'Ciudad': res} if res else {}

    def _uy_cfe_A50_Departamento(self):
        self.ensure_one()
        res = self.company_id.state_id.name[:30]
        return {'Departamento': res} if res else {}

    def _uy_cfe_A64_DirRecep(self):
        """ A64 Direccion de Receptor. Sin Validación. Maximo 70 caracteres.

        Opcional para facturas e tickets regualres
        Requerido para e-Rem Loc, e-Fact Expo y sus relacionados, tambien e-Rem Expo. """
        self.ensure_one()
        res = ''
        if self.partner_id.street:
            res += self.partner_id.street
        if self.partner_id.street2:
            res += ' ' + self.partner_id.street2
        res = res[:70]
        return {'DirRecep': res} if res else {}

    def _uy_cfe_A65_CiudadRecep(self):
        res = False
        if self.partner_id.city:
            res = self.partner_id.city[:30]
        return {'CiudadRecep': res} if res else {}

    def _uy_cfe_A66_DeptoRecep(self):
        res = False
        if self.partner_id.state_id:
            res = self.partner_id.state_id.name[:30]
        return {'DeptoRecep': res} if res else {}

    def _uy_cfe_A66_1_PaisRecep(self):
        res = False
        if self.partner_id.country_id:
            res = self.partner_id.country_id.name
        return {'PaisRecep': res} if res else {}

    def _uy_cfe_A68_InfoAdicional(self):
        res = False
        if self.l10n_uy_extra_info_cfe:
            res = self.l10n_uy_extra_info_cfe
        return {'InfoAdicional': res} if res else {}

    def _uy_cfe_A69_LugarDestEnt(self):
        res = False
        if self.l10n_uy_place_of_delivery:
            res = self.l10n_uy_place_of_delivery
        return {'LugarDestEnt': res} if res else {}

    def _is_uy_inv_type_cfe(self):
        return self.l10n_latam_document_type_id.internal_type in ['invoice', 'credit_note', 'debit_note']

    def _is_uy_remito_type_cfe(self):
        return self.l10n_latam_document_type_id.internal_type in ['stock_picking']

    def _is_uy_remito_exp(self):
        return self.l10n_latam_document_type_id.code == '124'

    def _is_uy_remito_loc(self):
        return self.l10n_latam_document_type_id.code == '181'

    def _is_uy_resguardo(self):
        return self.l10n_latam_document_type_id.code in ['182', '282']

    def is_expo_cfe(self):
        """ True of False in the current CFE is an exportation type  de tipo factura"""
        self.ensure_one()
        return int(self.l10n_latam_document_type_id.code) in [121, 122, 123]
        # TODO add codes for etiqueta e-remito exportcion

    @api.model
    def _l10n_uy_get_min_by_unidad_indexada(self):
        return self.env.ref('base.UYI').inverse_rate * 5000

    def _l10n_uy_get_cfe_tag(self):
        self.ensure_one()
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code in [101, 102, 103, 201]:
            return 'eTck'
        elif cfe_code in [111, 112, 113]:
            return 'eFact'
        elif cfe_code in [121, 122, 123]:
            return 'eFact_Exp'
        elif self._is_uy_remito_loc():
            return 'eRem'
        # elif self._is_uy_remito_exp():
        #     return 'eRem_Exp'
        # elif self._is_uy_resguardo():
        #     return 'eResg'
        else:
            raise UserError(
                _('Este tipo de comprobante aun no ha sido implementado') +
                " %s" % self.l10n_latam_document_type_id.display_name)

    def _l10n_uy_get_remito_codes(self):
        """ return list of the available document type codes for uruguayan of stock picking"""
        # self.ensure_one()
        # if self.picking_type_code != 'outgoing':
        #     return []
        return ['0', '124', '181', '224', '281']

    def _l10n_uy_get_cfe_adenda(self):
        """ Las adendas son opcionales, tenemos dos tipos de adenda:

        * Global: La configuramos en el menu Adenda, si el comprobante cumple la condición definida en la adenda
        entonces automaticamente se agrega como adenda al comprobante al enviar los datos auruware.

        * Especifica:
            * Si un comprobante tiene algo en el campo Referencia, esta se agrega como parte de la adenda con el
            prefijo "Referencia: ..."
            * Si la factura tiene terminos y condiciones, se agrega como adenda.
            * Si el picking tiene internal notes se agregan como adenda del e-remito

        La Adenda es una sección J en el CFE:
        * Es condicional para los tipos de documento de tipo facturas locales
        * Son opcionales en el e-Rem, y todos Documents de Expo

        NOTA: Actualmente no tenemos una manera de previsualizar desde la factura las adendas que se quieren aplicar """
        self.ensure_one()
        adenda = ''
        recordtype = {'account.move': 'inv', 'stock.picking': 'picking', 'account.move.line': 'aml'}
        context = {recordtype.get(self._name): self}
        for rec in self.company_id.l10n_uy_adenda_ids.filtered(lambda x: x.apply_on in ['all', self._name]):
            if bool(safe_eval.safe_eval(rec.condition, context)) == True:
                adenda += "\n\n" + rec.content

        # Si el comprobante/factura tiene una referencia entonces agregarla para que se muestre al final de la Adenda
        fieldname = {'account.move': 'ref', 'stock.picking': 'origin', 'account.move.line': 'name'}.get(self._name)
        if self[fieldname]:
            adenda += "\n\nReferencia: %s" % self[fieldname]

        # Si el comprobante/factura tiene Terminos y Condiciones/Observaciones, se agrega en la Adenda
        fieldname = {
            'account.move': 'narration',
            'stock.picking': 'note',
            # 'account.move.line': 'internal_notes' no hay un campo aca para lo que podamos usar como adenda.
        }.get(self._name)
        if fieldname and self[fieldname]:
            adenda += "\n\n%s" % html2plaintext(self[fieldname])

        if adenda:
            return {'Adenda': adenda.strip()}
        return {}

    def _l10n_uy_get_cfe_serie(self):
        # TODO Si soy ticket de contingencia usar los valores que estan definidos en el Odoo """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
                # TODO KZ esto va a explocar tocaria hacerlo de otra manera,
                # solo para tickets contigencia
            })
        return res

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

    def _uy_cfe_A113_MntExpoyAsim(self, res):
        """ Si tipo de CFE= 124 (e-remito de exportación):
            * Suma de ítems del e-remito de exportación Menos Suma de ítems del e-remito de exportación con indicador de facturación (B- C4)=8
            * Sino, Suma de ítems de exportación y asimilados, menos descuentos globales más recargos globales (asignados a ítems de exportación

        Es de tipo NUM 17 - -Valor numérico de 15 enteros y 2 decimales

        * Es condicional para los docs regulares.
        * No corresponde si es de tipo e-Rem
        * es Obligatorio si es cualquier tipo de tipo Expo incluyendo e-Rem Exp.

        Si A-C2=124, C113= ∑B-C24 - ∑B-C24 (si B- C4=8), sino
        C113= ∑ B-C24 (si B-C4=10) menos ∑ D-C6 (si D-C7=10 y si D- C2=D) más ∑ D-C6 (si D-C7=10 y si D- C2=R))
        """
        if self.is_expo_cfe() or self._is_uy_remito_exp():
            res.update({
                'MntExpoyAsim': float_repr(self.amount_total, 2),
            })
        return res

    def _l10n_uy_get_cfe_totals(self):
        self.ensure_one()
        res = {}

        # A110 Tipo moneda transacción: Informar para todos menos para e-Rem loc
        if not self._is_uy_remito_loc():
            res['TpoMoneda'] = self._l10n_uy_get_currency()

        # A124 Total Monto Total (NUM 17)
        # - Si tipo de CFE= 124 (e-remito de exportación), Valor numérico de 15 enteros y 2 decimales:
        # - sino, Valor numérico de 15 enteros y 2 decimales, ≥0 : C124 = SUM(C112:C118) + SUM(C121:C123)
        if not self._is_uy_remito_loc() and not self._is_uy_resguardo():
            res['MntTotal'] = float_repr(self.amount_total, 2)

        lines = self._uy_get_cfe_lines()
        res['CantLinDet'] =  len(lines)  # A126

        # A130 Monto Total a Pagar (NO debe ser reportado si de tipo remito u e-resguardo)
        if not self._is_uy_remito_type_cfe() and not self._is_uy_resguardo():
            res['MntPagar'] = float_repr(self.amount_total, 2)
            # TODO Esto toca adaptarlo cuando agreguemos retenciones y percepciones ya que representa la
            # "Suma de (monto total + valor de la retención/percepción + monto no facturable)

        # A111 Tipo de Cambio: Informar siempre que la moneda sea diferente al peso Uruguayo y no sea e-Rem Loc
        if not self._is_uy_remito_loc() and self._l10n_uy_get_currency() != 'UYU':
            res['TpoCambio'] = float_repr(self.l10n_uy_currency_rate, 3)
            if self.l10n_uy_currency_rate <= 0.0:
                raise UserError(_('Not valid Currency Rate, need to be greather that 0 in order to be accepted by DGI'))

        self._uy_cfe_A113_MntExpoyAsim(res)

        # Solo si es tipo de documento local de tipo factura (Es decir si no es e-Exp o e-Rem)
        if self._is_uy_inv_type_cfe() and not self.is_expo_cfe():
            self._check_uruguayan_invoices()

            # TODO this need to be improved, using a different way to print the tax information
            tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes(self.company_id)

            amount_field = 'amount_currency'
            tax_line_exempt = self.line_ids.filtered(lambda x: tax_vat_exempt in x.tax_ids)
            if tax_line_exempt and not self.is_expo_cfe():
                res.update({
                    'MntNoGrv': float_repr(abs(sum(tax_line_exempt.mapped(amount_field))), 2),  # A112 Total Monto - No Gravado
                })

            # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
            # usamos price_subtotal en lugar de otro campo
            tax_line_basica = self.line_ids.filtered(lambda x: tax_vat_22 in x.tax_line_id)
            if tax_line_basica:
                base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_22 in x.tax_ids).mapped(amount_field))
                res.update({
                    # A117 Total Monto Neto - IVA Tasa Basica
                    'MntNetoIVATasaBasica': float_repr(abs(base_imp), 2),

                    # A120 Tasa Mínima IVA TODO
                    'IVATasaBasica': 22,
                    # A122 Total IVA Tasa Básica? Monto del IVA Tasa Basica
                    'MntIVATasaBasica': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

            tax_line_minima = self.line_ids.filtered(lambda x: tax_vat_10 in x.tax_line_id)
            if tax_line_minima:
                base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_10 in x.tax_ids).mapped(amount_field))
                res.update({
                    # A-C116 Total Monto Neto - IVA Tasa Minima
                    'MntNetoIvaTasaMin': float_repr(abs(base_imp), 2),
                    # A119 Tasa Mínima IVA TODO
                    'IVATasaMin': 10,
                    # A-C121 Total IVA Tasa Básica? Monto del IVA Tasa Minima
                    'MntIVATasaMin': float_repr(abs(tax_line_minima[amount_field]), 2),
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

    def _uy_cfe_A5_FchEmis(self):
        """ A5 FchEmis. Fecha del Comprobante """
        self.ensure_one()
        if self._is_uy_inv_type_cfe():
            return self.date.strftime('%Y-%m-%d')
        if self._is_uy_remito_type_cfe():
            # TODO KZ ver que fecha deberiamos de usar en caso de ser picking. opciones
            #   scheduled_date - Scheduled Date
            #   date - Creation Date
            #   date_deadline - Deadline
            #   date_done - Date of Transfer
            return self.scheduled_date.strftime('%Y-%m-%d')
        raise UserError(_('FchEmis: No implementado para este tipo de CFE'))

    def _l10n_uy_get_cfe_iddoc(self):
        res = {'FchEmis': self._uy_cfe_A5_FchEmis()}
        if self._is_uy_inv_type_cfe():
            res.update({
                'FchVenc': self.invoice_date_due.strftime('%Y-%m-%d'),
                'FmaPago': 1 if self.l10n_uy_payment_type == 'cash' else 2,
            })

        if self._is_uy_remito_type_cfe(): # A6
            res.update({'TipoTraslado': self.l10n_uy_transfer_of_goods})

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
            'IdDoc': self._l10n_uy_get_cfe_iddoc(),
            'item_detail': self._l10n_uy_get_cfe_item_detail(),
            'totals_detail': self._l10n_uy_get_cfe_totals(),
            'receptor': self._l10n_uy_get_cfe_receptor(),
            'emisor': self._l10n_uy_get_cfe_emisor(),
            'cfe_tag': self._l10n_uy_get_cfe_tag(),
            'referencia_lines': self._l10n_uy_get_cfe_referencia(),
        }
        cfe = self.env['ir.qweb']._render('l10n_uy_edi.cfe_template', values)
        cfe = cfe.unescape()
        cfe = '\n'.join([item for item in cfe.split('\n') if item.strip()])

        return {'cfe_str': cfe}

    def _uy_get_cfe_lines(self):
        self.ensure_one()
        if self._is_uy_inv_type_cfe():
            return self.invoice_line_ids.filtered(lambda x: x.display_type in ('product'))
        if self._is_uy_remito_type_cfe():
            # TODO KZ: Toca revisar realmente cual es el line que corresponde, el que veo en la interfaz parece ser move_ids_without_package pero no se si esto siempre aplica

            # move_ids_without_package	Stock moves not in package (stock.move)
            # move_line_ids	Operations (stock.move.line)
            # move_line_ids_without_package	Operations without package (stock.move.line)
            return self.move_ids_without_package

    def _uy_cfe_B7_NomItem(self, line):
        """B7 Nombre del ítem (producto o servicio). Maximo 80 caracteres
        """
        self.ensure_one()
        if self._is_uy_inv_type_cfe() or self._is_uy_remito_type_cfe():
            if line.product_id:
                return line.product_id.display_name[:80]
            else:
                return line.name[:80]

    def _uy_cfe_B8_DscItem(self, line):
        """B8 Descripcion Adicional del ítem. Maximo 1000 caracteres
        """
        self.ensure_one()
        res = False
        if self._is_uy_inv_type_cfe():
            if line.product_id.display_name != line.name:
                res = line.name[:1000]
        if self._is_uy_remito_type_cfe():
            res = line.description_picking[:1000]
        return {'DscItem': res} if res else {}

    def _uy_cfe_B9_Cantidad(self, line):
        """ # B9 Cantidad. Valor numerico 14 enteros y 3 decimales
        """
        # TODO OJO se admite negativo? desglozar
        self.ensure_one()
        res = 0.0
        if self._is_uy_inv_type_cfe():
            res = line.quantity
        elif self._is_uy_remito_type_cfe():
            res = line.quantity_done

        return float_repr(res, 3)

    def _uy_cfe_B11_PrecioUnitario(self, line, IndFact):
        """ B11: Precio Unitario. Valor numérico de 11 enteros y 6 decimales >0, excepto:

            * Si B-C4=5, B-C11 debe ser 0
            * Si B-C4=8, B-C11 puede ser ≥0
            Donde B4 es "Indicador de facturación" (IndFact)

        Obligatorio informar para todos exepto para e-Remito Local o e-Resguardo (no corresponde) """
        res = False
        self.ensure_one()
        if self._is_uy_inv_type_cfe():
            line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
            subtotal = 1 * line_discount_price_unit
            res = float_repr(subtotal, 6)
        if self._is_uy_remito_exp():
            if IndFact == 5:
                res = float_repr(0, 6)
            elif IndFact == 8:
                raise UserError(_('No esta implementado usar indicador de facturación 8.  corresponde a un ítem a rebajar de otro remito ya emitido'))
                # TODO: devolver el precio unitario de ese producto, la cosa es que no consegui una relacion directa entre el aml y el sml.
            else:
                res = line.quantity_done
        return {'PrecioUnitario': res} if res else {}

    def _uy_cfe_B24_MontoItem(self, line):
        """ B24: Monto Item. Valor por linea de detalle. Valor numérico de 15 enteros y 2 decimales

        - Debe ser cero cuando: C4=5
        - Calculo C24 = (B-C9 * B-C11) – B-C13 + B-C17

        Donde:
            B-C4: Indicador de Facturacion. 4 - Gravado a otra tasa/iva sobre fictos.
            B-C9: Cantidad
            B-C11 Precio unitario
            B-C13 Monto Descuento
            B-C17 Monto Recargo

        No corresponde para e-Rem pero es obligatorio para e-Rem Exp
        """
        # TODO en futuro para incluir descuentos B24=(B9*B11)–B13+B17
        if self._is_uy_inv_type_cfe():
            return float_repr(line.price_subtotal, 2)
        if self._is_uy_remito_type_cfe():
            if self._is_uy_remito_exp():
                raise UserError(_('No esta implementado el e-Remito Exportación'))

            return False

    def _l10n_uy_get_cfe_item_detail(self):
        """ Devuelve una lista con los datos que debemos informar por linea de factura en el CFE
        Seccion B Detalle de Productos y Servicios del XML
        """
        res = []
        lines = self._uy_get_cfe_lines()

        # Verificar restriccion de cantidad maxima de lineas que podemos informar, lanzar exepcion previa desde Odoo para
        # evitar enviar y recibir un rechazo por DGI

        # e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección: Hasta 700
        if self.l10n_latam_document_type_id.code in [101, 102, 103, 131, 132, 133] and len(lines) > 700:
            raise UserError('Para e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección solo puede'
                            ' reportar Hasta 700')
        # Otros CFE: Hasta 200
        elif len(lines) > 200:
            raise UserError('Para este tipo de CFE solo puede reportar hasta 200 lineas')

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo

        for k, line in enumerate(lines, 1):
            item = {}
            item.update(self._uy_cfe_B4_IndFact(line))
            item.update({
                'NroLinDet': k,  # B1 No de línea o No Secuencial. a partir de 1
                'NomItem': self._uy_cfe_B7_NomItem(line),
                'Cantidad': self._uy_cfe_B9_Cantidad(line),
                'UniMed': self._uy_cfe_B10_UniMed(line),
                'MontoItem': self._uy_cfe_B24_MontoItem(line),  # B24 Monto Item
            })
            item.update(self._uy_cfe_B11_PrecioUnitario(line, item.get('IndFact')))
            item.update(self._uy_cfe_B8_DscItem(line))
            res.append(item)

        return res

    def _uy_cfe_B10_UniMed(self, line):
        if self._is_uy_inv_type_cfe():
            return line.product_uom_id.name[:4] if line.product_uom_id else 'N/A'
        if self._is_uy_remito_type_cfe():
            return line.product_uom.name[:4] if line.product_uom else 'N/A'

    def _uy_cfe_B4_IndFact(self, line):
        """ B4: Indicador de facturación

        Indica si el producto o servicio es exento, o a que tasa está gravado o si corresponde a un concepto no
        facturable.

        En la docu de DGI dice N/A para e-remito y e-remito de exportación, excepto:
            * usar indicador de facturación 8 si corresponde a un ítem a rebajar de otro remito ya emitido,
            * usar indicador de facturación 5 si corresponde a un ítem con valor unitario igual a cero (sólo para e-remito de exportación).

        * Donde argumento line es:
            * ser un account.move.line para el caso de account.move,
            * ser un stock.move para el caso de stock.picking

            TODO KZ: Toca revisar realmente cual es el line que corresponde, el que veo en la interfaz parece ser move_ids_without_package pero no se si esto siempre aplica
                move_ids_without_package	Stock moves not in package (stock.move)
                move_line_ids	Operations (stock.move.line)
                move_line_ids_without_package	Operations without package (stock.move.line)
        """
        # TODO por ahora, esto esta solo funcionando para un impuesto de tipo iva por cada linea de factura, debemos
        # implementar el resto de los casos
        self.ensure_one()
        res = False
        if len(line) != 1:
            raise UserError(_('Solo se puede calcular el Indice de Factura por cada linea'))

        if self._is_uy_remito_type_cfe():
            # Solo implementamos por los momentos en el N/A
            res = False

        elif self._is_uy_inv_type_cfe():
            if self.is_expo_cfe():
                res = 10  # Exportación y asimiladas
            else:
                vat_taxes = self.env['account.tax']._l10n_uy_get_taxes(self.company_id)
                tax_vat_22, tax_vat_10, tax_vat_exempt = vat_taxes
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

                # NOTA IMPORTANTE: Por el momento solo enviamos la informacion de los impuestos de tipo iva.
                res = value.get(line.tax_ids.filtered(lambda x: x in vat_taxes).id)

        return {'IndFact': res} if res else {}

    def _uy_found_related_cfe(self):
        raise UserError(_("Not implemented found related cfe for") + " %s" % self._name)

    def _l10n_uy_get_cfe_referencia(self):
        res = []
        # If is a debit/credit note cfe then we need to inform el tag referencia
        if self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note']:
            related_cfe = self._uy_found_related_cfe()
            if not related_cfe:
                raise UserError(_('Para validar una ND/NC debe informar el Documento de Origen'))
            for k, related_cfe in enumerate(self._uy_found_related_cfe(), 1):
                document_number = re.findall(r"([A-Z])[-]*([0-9]*)", related_cfe.l10n_latam_document_number)[-1]

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

    def action_l10n_uy_get_pdf(self):
        """ Call query webservice to print pdf format of the CFE
        7.1.9 Representación impresa estándar de un CFE emitido en formato PDF
        return: create attachment in the move and automatica download """
        # TODO cada vez que corremos intenta imprimir el existente, borrar el attachment para volver a generar

        prefix = {
            'INV': 'account.move',
            'REMITO': 'stock.picking',
            'RESGUARDO': 'account.move.line',
        }
        if not self.l10n_uy_cfe_pdf:
            if self._name == 'account.move':
                if 'out' in self.move_type:
                    rut_field = 'rut'
                    rut_value = self.company_id.partner_id.vat
                elif 'in' in self.move_type:
                    # TODO esto no se ha probado aun
                    rut_field = 'rutRecibido'
                    rut_value = self.partner_id.vat
                else:
                    raise UserError(_('No se puede imprimir la representación Legal de este documento'))
            else:
                rut_field = 'rut'
                rut_value = self.company_id.partner_id.vat

            document_number = re.search(r"([A-Z]*)([0-9]*)", self.l10n_latam_document_number).groups()
            req_data = {
                rut_field: rut_value,
                'tipoCfe': int(self.l10n_latam_document_type_id.code),
                'serieCfe': document_number[0],
                'numeroCfe': document_number[1],
            }

            # En caso de que el contenido de las adendas sea mayor a 799 caracteres, la adenda se imprimira en
            # la segunda pagina de forma automatica, caso contrario, el cliente podra elegir el tipo de reporte que quiera
            # Si no elige ningun tipo de reporte, se imprimira el default de uruware
            records = self.env['l10n.uy.adenda'].sudo().search([('apply_on', '=', 'all') or ('apply_on', '=', 'account.move')])
            caract = 0
            for rec in records:
                caract += len(rec.content)
            if caract > 799:
                report_params = [['adenda'],['true']]
            else:
                #En caso de que el cliente quiera imprimir el reporte secundario
                report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or '[]')

            if report_params:
                nombreParametros = report_params[0]
                valoresParametros = report_params[1]
                versionPdf = 'ObtenerPdfConParametros'
                req_data.update({
                    'nombreParametros': nombreParametros,
                    'valoresParametros': valoresParametros,
                })
            else:
                versionPdf = 'ObtenerPdf'

            response = self.company_id._l10n_uy_ucfe_query(versionPdf, req_data)
            self.l10n_uy_cfe_pdf = self.env['ir.attachment'].create({
                'name': (self.name or prefix.get(self._name, 'OBJ')).replace('/', '_') + '.pdf',
                'res_model': self._name, 'res_id': self.id,
                'type': 'binary', 'datas': base64.b64encode(response)
            })
        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=ir.attachment&id=" + str(self.l10n_uy_cfe_pdf.id) +
            "&filename_field=name&field=datas&download=true&name=" + self.l10n_uy_cfe_pdf.name,
            'target': 'self'
        }

    def action_l10n_uy_validate_cfe(self):
        """ Be able to validate a cfe """
        self._l10n_uy_vaidate_cfe(self.sudo().l10n_uy_cfe_xml, raise_exception=True)

    def action_l10n_uy_preview_xml(self):
        """ Be able to show preview of the CFE to be send """
        self.l10n_uy_cfe_xml = self._l10n_uy_create_cfe().get('cfe_str')

    def _dummy_dgi_validation(self):
        """ Only when we want to skip DGI validation in testing environment. Fill the DGI result  fields with dummy
        values in order to continue with the CFE validation without passing to DGI validations s"""
        # TODO need to update to the result we need, all the fields we need to add are not defined yet
        self.write({
            'l10n_uy_cfe_uuid': '123456',
        })
        self.message_post(body=_('Validated locally because is not Uruware parameters are not properly configured'))

    def check_uy_state(self):
        for record in self:
            # The move cannot be modified once has been sent to UCFE
            if record.l10n_uy_ucfe_state in record._uy_cfe_already_sent():
                raise UserError(_('The operation can not be done. This %s has been already sent to UCFE')
                                % record.l10n_latam_document_type_id.name)
            # The move cannot be modified once the CFE has been accepted by the DGI
            elif record.l10n_uy_ucfe_state == '00':
                raise UserError(_('The operation can not be done. This %s is accepted by DGI.') % record.l10n_latam_document_type_id.name)

    def _l10n_uy_get_uuid(self):
        self.ensure_one()
        return self._name + '-' + str(self.id)

    def _l10n_uy_dgi_post(self):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """

        self._l10n_uy_validate_company_data()
        for rec in self:
            now = datetime.utcnow()
            CfeXmlOTexto = rec._l10n_uy_create_cfe().get('cfe_str')
            rec._l10n_uy_vaidate_cfe(CfeXmlOTexto)
            req_data = {
                'Uuid': self._l10n_uy_get_uuid(),
                'TipoCfe': int(rec.l10n_latam_document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto}

            req_data.update(rec._l10n_uy_get_cfe_adenda())
            req_data.update(rec._l10n_uy_get_cfe_serie())
            response, transport = rec.company_id._l10n_uy_ucfe_inbox_operation('310', req_data, return_transport=1)

            rec = rec.sudo()
            rec.l10n_uy_ucfe_state = response.Resp.CodRta
            rec._update_l10n_uy_cfe_state()

            # Si conseguimos un error de factura electronica directamente hacemos rollback: para que la factura de odoo
            # quede en borrador y no tengamos quede posteada y tengamos que cancelarla luego
            if 'error' in rec.l10n_uy_cfe_state:
                self.env.cr.rollback()

            rec.l10n_uy_ucfe_state = response.Resp.CodRta
            rec._update_l10n_uy_cfe_state()
            rec.l10n_uy_cfe_xml = CfeXmlOTexto
            rec.l10n_uy_dgi_xml_response = transport.xml_response
            rec.l10n_uy_dgi_xml_request = transport.xml_request
            rec.l10n_uy_cfe_uuid = response.Resp.Uuid
            rec.l10n_uy_ucfe_msg = response.Resp.MensajeRta
            rec.l10n_uy_ucfe_notif = response.Resp.TipoNotificacion

            if response.Resp.CodRta not in rec._uy_cfe_already_sent():
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
            rec.l10n_latam_document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)

            # TODO this one is failing, review why
            rec.l10n_uy_cfe_file = self.env['ir.attachment'].create({
                'name': 'CFE_{}.xml'.format(rec.l10n_latam_document_number),
                'res_model': self._name, 'res_id': rec.id,
                'type': 'binary', 'datas': base64.b64encode(CfeXmlOTexto.encode('ISO-8859-1'))}).id

            # If the record has been posted automatically print and attach the legal record reporte to the record.
            if 'error' not in rec.l10n_uy_cfe_state:
                rec.action_l10n_uy_get_pdf()

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

        return response
