import base64

from odoo import api,  models, fields, _

from odoo.exceptions import UserError
from odoo.tools import html2plaintext


class StockPicking(models.Model):

    _inherit = 'stock.picking'

    # Need to make it work with document types
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Document Type (UY)', copy=False)
    l10n_latam_document_number = fields.Char(string='Document Number (UY)', readonly=True, copy=False)
    l10n_latam_available_document_type_ids = fields.Many2many('l10n_latam.document.type', compute='_compute_l10n_latam_available_document_types')

    # Need to make it work with EDI (simil to what we have in account.move)
    l10n_uy_edi_document_id = fields.Many2one("l10n_uy_edi.document", string="Uruguay E-Invoice CFE", copy=False)
    l10n_uy_edi_cfe_uuid = fields.Char(related="l10n_uy_edi_document_id.uuid")
    l10n_uy_edi_cfe_state = fields.Selection(related="l10n_uy_edi_document_id.state", store=True)
    l10n_uy_edi_error = fields.Text(related="l10n_uy_edi_document_id.message")
    l10n_uy_edi_addenda_ids = fields.Many2many(
        "l10n_uy_edi.addenda",
        string="Addenda & Disclosure",
        domain="[('type', 'in', ['issuer', 'receiver', 'cfe_doc', 'addenda'])]",
        help="Addendas and Mandatory Disclosure to add the CFE, their are text added to the issuer, receiver, cfe doc"
        " additional info section or to the addenda section (item type should not be set in this field instead should"
        " be on the invoice lines)")
    l10n_uy_edi_cfe_sale_mode = fields.Selection([
        ("1", "General Regime"),
        ("2", "Consignment"),
        ("3", "Reviewable Price"),
        ("4", "Own goods to customs exclaves"),
        ("90", "General Regime - exportation of services"),
        ("99", "Other transactions"),
    ], "Sales Modality", help="This field is used in the XML to create an Export e-Invoice")
    l10n_uy_edi_cfe_transport_route = fields.Selection([
        ("1", "Maritime"),
        ("2", "Air"),
        ("3", "Ground"),
        ("8", "N/A"),
        ("9", "Other"),
    ], "Transportation Route", help="This field is used in the XML to create an Export e-Invoice")

    # New fields only for pickings
    l10n_uy_transfer_of_goods = fields.Selection(
        [('1', 'Venta'),
         ('2', 'Traslados internos')],
        string="Traslados de Bienes",
    )
    l10n_uy_edi_place_of_delivery = fields.Boolean(
        "Place of Delivery",
        size=100,
        help="CFE: Indication of where the merchandise is delivered or the service is provided"
        " (Address, Branch, Port, etc.) if True then we will inform the shipping address's name and street")

    # TODO KZ campo similar a lo que tenemos en el UX, revisar como se llama y usarlo igual
    l10n_uy_cfe_xml = fields.Text()

    def name_get(self):
        """ Display: 'Stock Picking Internal Sequence : Remito Number (if defined)' """
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
        """ return domain """
        codes = self._l10n_uy_get_remito_codes()
        return [('code', 'in', codes), ('active', '=', True), ('internal_type', '=', 'stock_picking')]

    def action_cancel(self):
        """ El remito no puede ser modificado una vez que ya fue aceptado por DGI """
        remitos = self.filtered(lambda x: x.country_code == 'UY' and x.picking_type_code == 'outgoing')
        if remitos.filtered(lambda x: x.l10n_uy_edi_cfe_state in ['accepted', 'rejected', 'received']):
            raise UserError(_('Can not cancel a Remito already process by DGI'))
        return super().action_cancel()

    def l10n_uy_edi_stock_post_dgi(self):
        """ El E-remito tiene las siguientes partes en el xml
            A. Encabezado
            B. Detalle de los productos
            C. Subtotales Informativos (opcional)
            F. Informacion de Referencia (condicional)
        """
        # Filtrar solo los e-remitos
        uy_remitos = self.filtered(
            lambda x: x.country_code == 'UY'
            and x.picking_type_code == 'outgoing'
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_edi_cfe_state not in ['accepted', 'rejected', 'received']
        )

        # If the invoice was previously validated in Uruware and need to be link to Odoo
        # we check that the l10n_uy_edi_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_remitos.filtered(lambda x: x.l10n_uy_edi_cfe_uuid and not x.attachment_id and not x.l10n_uy_edi_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.uy_ux_action_get_uruware_cfe()
            uy_remitos = uy_remitos - pre_validated_in_uruware

        if not uy_remitos:
            return

        # Send invoices to DGI and get the return info
        for remito in uy_remitos:
            if remito.company_id.l10n_uy_edi_ucfe_env == "demo":
                attachments = remito._l10n_uy_edi_dummy_validation()
                msg = _(
                    "This CFE has been generated in DEMO Mode. It is considered"
                    " as accepted and it won\"t be sent to DGI.")
            else:
                remito._uy_dgi_post()
                msg += _("The electronic invoice was created successfully")

            remito.with_context(no_new_invoice=True).message_post(
                body=msg, attachment_ids=attachments.ids if attachments else False)

    def _l10n_uy_edi_dummy_validation(self):
        # COPY l10n_uy_edi (only change move_id with picking_id)
        """ When we want to skip DGI and validate only in Odoo """
        edi_doc = self.l10n_uy_edi_document_id
        edi_doc.state = "accepted"
        self.write({
            "l10n_latam_document_number": "DE%07d" % (edi_doc.picking_id.id),
            "ref": "*DEMO",
        })

        return self._l10n_uy_edi_get_preview_xml()

    def _l10n_uy_edi_get_preview_xml(self):
        # COPY l10n_uy_edi
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        edi_doc.attachment_id.res_field = False
        xml_file = self.env["ir.attachment"].create({
            "res_model": "l10n_uy_edi.document",
            "res_field": "attachment_file",
            "res_id": edi_doc.id,
            "name": edi_doc._get_xml_attachment_name(),
            "type": "binary",
            "datas": base64.b64encode(self._l10n_uy_edi_get_xml_content().encode()),
        })
        edi_doc.invalidate_recordset(["attachment_id", "attachment_file"])
        return xml_file

    def _l10n_uy_edi_get_xml_content(self):
        # COPY l10n_uy_edi
        """ Create the CFE xml structure and validate it
            :return: string the xml content to send to DGI """
        self.ensure_one()

        values = {
            "cfe": self,
            "IdDoc": self._l10n_uy_edi_cfe_A_iddoc(),
            "emisor": self._l10n_uy_edi_cfe_A_issuer(),
            "receptor": self._l10n_uy_edi_cfe_A_receptor(),
            "item_detail": self._l10n_uy_edi_cfe_B_details(),
            "totals_detail": self._l10n_uy_edi_cfe_C_totals(),
            "referencia_lines": self._l10n_uy_edi_cfe_F_reference(),
            "format_float": format_float,
        }
        cfe = self.env["ir.qweb"]._render(
            "l10n_uy_edi." + self.l10n_uy_edi_document_id._get_cfe_tag(self) + "_template", values)
        return etree.tostring(cleanup_xml_node(cfe)).decode()

    def _l10n_uy_edi_get_addenda(self):
        """ return string with the addenda of the remito """
        addenda = self.l10n_uy_edi_document_id._get_legends("addenda", self)
        if self.origin:
            addenda += "\n\nOrigin: %s" % self.origin
        if self.note:
            addenda += "\n\n%s" % html2plaintext(self.note)
        return addenda.strip()

    def _l10n_uy_edi_get_used_rate(self):
        # COPY l10n_uy_edi
        self.ensure_one()
        # We need to use abs to avoid error on Credit Notes (amount_total_signed is negative)
        return abs(self.amount_total_signed) / self.amount_total

    def _l10n_uy_edi_cfe_C_totals(self):
        self.ensure_one()
        currency_name = self.currency_id.name if self.currency_id else self.company_id.currency_id.name
        lines = self._uy_get_cfe_lines()
        res = {
            'TpoMoneda': currency_name if not self._is_uy_remito_loc() else None,  # A110
            'TpoCambio': None if currency_name == "UYU" else self._l10n_uy_edi_get_used_rate() or None,  # A111
            'CantLinDet': len(lines),  # A126
        }
        return res

    def _uy_get_cfe_lines(self):
        self.ensure_one()
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

