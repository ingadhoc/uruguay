from odoo import api,  models, fields, _
from odoo.tools import html2plaintext


class StockPicking(models.Model):

    _name = 'stock.picking'
    _inherit = ['l10n.uy.cfe', 'stock.picking']

    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Document Type (UY)', copy=False)
    l10n_latam_document_number = fields.Char(string='Document Number (UY)', readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    l10n_latam_available_document_type_ids = fields.Many2many('l10n_latam.document.type', compute='_compute_l10n_latam_available_document_types')
    l10n_uy_transfer_of_goods = fields.Selection(
        [('1', 'Venta'),
         ('2', 'Traslados internos')],
        string="Traslados de Bienes",
    )

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
            and x.l10n_uy_ucfe_state not in x._uy_cfe_already_sent()
        )

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_remitos.filtered(lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()
            uy_remitos = uy_remitos - pre_validated_in_uruware

        if not uy_remitos:
            return

        # Send invoices to DGI and get the return info
        for remito in uy_remitos:
            if remito._uy_is_demo_env():
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
