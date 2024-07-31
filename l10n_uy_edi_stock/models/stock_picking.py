from odoo import api,  models, fields, _
from odoo.tools import html2plaintext


class StockPicking(models.Model):

    _inherit = 'stock.picking'

    l10n_uy_cfe_id = fields.Many2one("l10n_uy_edi.document", string="Uruguay E-Resguardo CFE", copy=False)
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Document Type (UY)', copy=False)
    l10n_latam_document_number = fields.Char(string='Document Number (UY)', readonly=True, states={'draft': [('readonly', False)]}, copy=False)

    # Fields that need to be fill before creating the CFE
    l10n_uy_edi_cfe_uuid = fields.Char(
        'Key or UUID CFE', help="Unique identification per CFE in UCFE. Currently is formed by the concatenation of model name initials plust record id", copy=False)
    l10n_uy_edi_addenda_ids = fields.Many2many(
        'l10n_uy_edi.addenda', string="Addenda & Disclosure",
        domain="[('type', 'in', ['issuer', 'receiver', 'cfe_doc', 'addenda'])]")

    l10n_latam_available_document_type_ids = fields.Many2many('l10n_latam.document.type', compute='_compute_l10n_latam_available_document_types')
    l10n_uy_transfer_of_goods = fields.Selection(
        [('1', 'Venta'), ('2', 'Traslados internos')],
        string="Traslados de Bienes",
    )

    l10n_uy_cfe_sale_mod = fields.Selection([
        ('1', 'General Regime'),
        ('2', 'Consignment'),
        ('3', 'Reviewable Price'),
        ('4', 'Own goods to customs exclaves'),
        ('90', 'General Regime - exportation of services'),
        ('99', 'Other transactions'),
    ], 'Sales Modality', help="This field is used in the XML to create an Export e-Delivery Guide")
    l10n_uy_cfe_transport_route = fields.Selection([
        ('1', 'Maritime'),
        ('2', 'Air'),
        ('3', 'Ground'),
        ('8', 'N/A'),
        ('9', 'Other'),
    ], 'Transportation Route', help="This field is used in the XML to create an Export e-Delivery Guide")
    l10n_uy_place_of_delivery = fields.Char(
        "Place of Delivery",
        size=100,
        help="Indicación de donde se entrega la mercadería o se presta el servicio (Dirección, Sucursal, Puerto, etc,)")
    l10n_uy_edi_place_of_delivery = fields.Boolean(
        "Place of Delivery",
        help="CFE: Indication of where the merchandise is delivered or the service is provided"
        " (Address, Branch, Port, etc.) if True then we will inform the shipping address's name and street")

    def name_get(self):
        """ Display: 'Stock Picking Internal Sequence : Remito (if defined)' """
        res = []
        for rec in self:
            if rec.l10n_latam_document_number:
                name = rec.name + ": (%s %s)" % (rec.l10n_latam_document_type_id.doc_code_prefix, rec.l10n_latam_document_number)
            else:
                name = rec.name
            res.append((rec.id, name))
        return res

    @api.depends('partner_id', 'company_id', 'picking_type_code')
    def _compute_l10n_latam_available_document_types(self):
        uy_remitos = self.filtered(lambda x: x.country_code == 'UY' and x.picking_type_code == 'outgoing')

        uy_remitos.l10n_latam_available_document_type_ids = self.env['l10n_latam.document.type'].search(
            self._get_l10n_latam_documents_domain())
        (self - uy_remitos).l10n_latam_available_document_type_ids = False

    def _get_l10n_latam_documents_domain(self):
        codes = self._l10n_uy_get_remito_codes()
        return [('code', 'in', codes), ('active', '=', True), ('internal_type', '=', 'stock_picking')]

    # TODO KZ evaluar si estaria bueno tener un boolean como este l10n_cl_draft_status
    # TODO KZ evaluar si agregar una constrains de unicidad para remitos, aplicaria para:
    #  1. remitos manual o preimpresos (no electronico),
    #  2. remitos generados en uruware y pasados a mano luego a oodo
    #  3. remitos de proveedor? no se si los necesitamos registrar

    def action_cancel(self):
        # The move cannot be modified once the CFE has been accepted by the DGI
        remitos = self.filtered(lambda x: x.country_code == 'UY' and x.picking_type_code == 'outgoing')
        remitos._uy_check_state()
        return super().action_cancel()

    def uy_post_dgi_remito(self):
        """ El E-remito tiene las siguientes partes en el xml
            A. Encabezado
            B. Detalle de los productos
            C. Subtotales Informativos (opcional)
            F. Informacion de Referencia (condicional)
        """
        # Filtrar solo los e-remitos
        uy_remitos = self.filtered(
            lambda x: x.country_code == 'UY' and x.picking_type_code == 'outgoing'
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_edi_cfe_state not in ['accepted', 'rejected', 'received']
        )

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_edi_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_remitos.filtered(lambda x: x.l10n_uy_edi_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_edi_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.uy_ux_action_get_uruware_cfe()
            uy_remitos = uy_remitos - pre_validated_in_uruware

        if not uy_remitos:
            return

        # Send invoices to DGI and get the return info
        for remito in uy_remitos:
            if remito.company_id.l10n_uy_edi_ucfe_env == "demo":
                remito._uy_dummy_validation()
                continue

            # TODO KZ I think we can avoid this loop. review
            remito._uy_dgi_post()

    # TODO KZ buscar el metodo _l10n_cl_get_tax_amounts para ejemplos de como extraer la info de los impuestos en un picking. viene siempre de una
    # factura

    def _uy_get_cfe_addenda(self):
        """ Add Specific MOVE model fields to the CFE Addenda if they are set:

        * field Origin added with the prefix "Origin: ..."
        * Observation
        """
        self.ensure_one()
        res = super()._uy_get_cfe_addenda()
        if self.origin:
            res += "\n\nOrigin: %s" % self.origin
        if self.note:
            res += "\n\n%s" % html2plaintext(self.note)
        return res.strip()

    def _uy_get_cfe_lines(self):
        self.ensure_one()
        if self._is_uy_remito_type_cfe():
            # TODO KZ: Toca revisar realmente cual es el line que corresponde, el que veo en la interfaz parece ser move_ids_without_package pero no se si esto siempre aplica

            # move_ids_without_package	Stock moves not in package (stock.move)
            # move_line_ids	Operations (stock.move.line)
            # move_line_ids_without_package	Operations without package (stock.move.line)
            return self.move_ids_without_package

    def _l10n_uy_get_remito_codes(self):
        """ return list of the available document type codes for uruguayan of stock picking"""
        # self.ensure_one()
        # if self.picking_type_code != 'outgoing':
        #     return []
        return ['0', '124', '181', '224', '281']

    def l10n_uy_edi_action_get_dgi_state(self):
        self.ensure_one()
        self.l10n_uy_edi_cfe_id.l10n_uy_edi_action_get_dgi_state()

    # TODO KZ este metodo esta en el account.move. debemos de generarlo tal cual en stock picking
    def _l10n_uy_edi_cfe_A_receptor(self):
        # EXTEND l10n_uy_edi
        """ Agregamos mas campos no obligatorios que no nos permitieron agregar en oficial """
        res = super()._l10n_uy_edi_cfe_A_receptor()
        # A69 - LugarDestEnt
        if self.l10n_uy_edi_place_of_delivery and not self._is_uy_resguardo():
            value = ''
            delivery_address = self.partner_shipping_id
            if delivery_address:
                value = (delivery_address.name + ' ' + delivery_address.street)[:100]
            res['LugarDestEnt'] = value

    def _uy_cfe_A_iddoc(self):
        res = super()._uy_cfe_A_iddoc()

        return res

    def _l10n_uy_edi_cfe_A_iddoc(self):
        res = self.env['account.move']._l10n_uy_edi_cfe_A_iddoc()

        if self._is_uy_remito_type_cfe():  # A6
            res.update({'TipoTraslado': self.l10n_uy_transfer_of_goods})

        # TODO KZ A5 FchEmis - Fecha del Comprobante -
        # ver que fecha deberiamos de usar en caso de ser picking. opciones
    #   scheduled_date - Scheduled Date
    #   date - Creation Date
    #   date_deadline - Deadline
    #   date_done - Date of Transfer
    #     return res
        # .   self.scheduled_date.strftime('%Y-%m-%d')

        res.update(self._l10n_uy_get_cfe_serie())

        return res


    # TODO KZ este metodo debemos adaptarlo para obtener el IndFact
    def _uy_cfe_B4_IndFact(self, line):
        """ B4: Indicador de facturación

            TODO KZ: Toca revisar realmente cual es el line que corresponde, el que veo en la interfaz parece ser move_ids_without_package pero no se si esto siempre aplica
                move_ids_without_package	Stock moves not in package (stock.move)
                move_line_ids	Operations (stock.move.line)
                move_line_ids_without_package	Operations without package (stock.move.line)
        """
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
        return super()._uy_cfe_B4_IndFact(line)
