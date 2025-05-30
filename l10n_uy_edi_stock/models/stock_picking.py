from odoo import api, fields, models


class StockPicking(models.Model):
    _name = "stock.picking"
    _inherit = ["l10n.uy.cfe", "stock.picking"]

    l10n_latam_document_type_id = fields.Many2one("l10n_latam.document.type", string="Document Type (UY)", copy=False)
    l10n_latam_document_number = fields.Char(
        string="Document Number (UY)", readonly=True, states={"draft": [("readonly", False)]}, copy=False
    )
    l10n_latam_available_document_type_ids = fields.Many2many(
        "l10n_latam.document.type", compute="_compute_l10n_latam_available_document_types"
    )
    l10n_uy_transfer_of_goods = fields.Selection(
        [("1", "Venta"), ("2", "Traslados internos")],
        string="Traslados de Bienes",
    )

    def name_get(self):
        """Display: 'Stock Picking Internal Sequence : Remito (if defined)'"""
        res = []
        for rec in self:
            if rec.l10n_latam_document_number:
                name = rec.name + ": (%s %s)" % (
                    rec.l10n_latam_document_type_id.doc_code_prefix,
                    rec.l10n_latam_document_number,
                )
            else:
                name = rec.name
            res.append((rec.id, name))
        return res

    @api.depends("partner_id", "company_id", "picking_type_code")
    def _compute_l10n_latam_available_document_types(self):
        uy_remitos = self.filtered(lambda x: x.country_code == "UY" and x.picking_type_code == "outgoing")

        uy_remitos.l10n_latam_available_document_type_ids = self.env["l10n_latam.document.type"].search(
            self._get_l10n_latam_documents_domain()
        )
        (self - uy_remitos).l10n_latam_available_document_type_ids = False

    def _get_l10n_latam_documents_domain(self):
        codes = self._l10n_uy_get_remito_codes()
        return [("code", "in", codes), ("active", "=", True), ("internal_type", "=", "stock_picking")]

    # TODO KZ evaluar si estaria bueno tener un boolean como este l10n_cl_draft_status
    # TODO KZ evaluar si agregar una constrains de unicidad para remitos, aplicaria para:
    #  1. remitos manual o preimpresos (no electronico),
    #  2. remitos generados en uruware y pasados a mano luego a oodo
    #  3. remitos de proveedor? no se si los necesitamos registrar

    def action_cancel(self):
        # The move cannot be modified once the CFE has been accepted by the DGI
        remitos = self.filtered(lambda x: x.country_code == "UY" and x.picking_type_code == "outgoing")
        remitos.check_uy_state()
        return super().action_cancel()

    def uy_post_dgi_remito(self):
        """El E-remito tiene las siguientes partes en el xml
        A. Encabezado
        B. Detalle de los productos
        C. Subtotales Informativos (opcional)
        F. Informacion de Referencia (condicional)
        """
        # Filtrar solo los e-remitos
        uy_remitos = self.filtered(
            lambda x: x.country_code == "UY"
            and x.picking_type_code == "outgoing"
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_ucfe_state not in x._uy_cfe_already_sent()
        )

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_remitos.filtered(
            lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_cfe_state
        )
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()
            uy_remitos = uy_remitos - pre_validated_in_uruware

        if not uy_remitos:
            return

        # Send invoices to DGI and get the return info
        for remito in uy_remitos:
            if remito._is_dummy_dgi_validation():
                remito._dummy_dgi_validation()
                continue

<<<<<<< HEAD
            # TODO KZ I think we can avoid this loop. review
            remito._l10n_uy_dgi_post()
||||||| parent of 9725768 (temp)
        return res

    def _l10n_uy_edi_get_addenda(self):
        """ return string with the addenda of the remito """
        addenda = self.l10n_uy_edi_document_id._get_legends("addenda", self)
        if self.origin:
            addenda += "\n\nOrigin: %s" % self.origin
        if self.note:
            addenda += "\n\n%s" % html2plaintext(self.note)
        return addenda.strip()

    def _l10n_uy_get_delivery_guide_codes(self):
        """ return list of the available document type codes for uruguayan of stock picking"""
        # self.ensure_one()
        # if self.picking_type_code != 'outgoing':
        #     return []
        return ['0', '181']

    # XML prepapre values

    def _l10n_uy_stock_prepare_req_data(self):
        """ Creating dictionary with the request to generate a DGI EDI document """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        xml_content = self._l10n_uy_stock_get_xml_content()
        req_data = {
            "Uuid": edi_doc.uuid,
            "TipoCfe": int(self.l10n_latam_document_type_id.code),
            "HoraReq": edi_doc.request_datetime.strftime("%H%M%S"),
            "FechaReq": edi_doc.request_datetime.date().strftime("%Y%m%d"),
            "CfeXmlOTexto": xml_content}

        if addenda := self._l10n_uy_edi_get_addenda():
            req_data["Adenda"] = addenda
        return req_data

    def _uy_get_cfe_lines(self):
        self.ensure_one()
        # En si cuando queda validado el remito siempre usa move_line_ids
        # move_ids_without_package	Stock moves not in package (stock.move)
        # move_line_ids	Operations (stock.move.line)
        # move_line_ids_without_package	Operations without package (stock.move.line)
        return self.move_ids_without_package

    def _l10n_uy_stock_get_xml_content(self):
        """ Create the CFE xml structure and validate it
            :return: string the xml content to send to DGI """
        self.ensure_one()
        template_name = "l10n_uy_edi_stock." + self.l10n_uy_edi_document_id._get_cfe_tag(self) + "_template"
        values = {
            "cfe": self,
            "res_model": self._name,
            "IdDoc": self._l10n_uy_stock_cfe_A_iddoc(),
            "emisor": self._l10n_uy_stock_cfe_A_issuer(),
            "receptor": self._l10n_uy_stock_cfe_A_receptor(),
            "totals_detail": self._l10n_uy_stock_cfe_A_totals(),
            "item_detail": self._l10n_uy_stock_cfe_B_details(),
            "referencia_lines": self._l10n_uy_edi_cfe_F_reference(),
            "format_float": format_float,
        }
        cfe = self.env["ir.qweb"]._render(template_name, values=values)
        return etree.tostring(cleanup_xml_node(cfe)).decode()

    def _l10n_uy_stock_cfe_A_iddoc(self):
        """ XML Section A (Encabezado) """
        values = {
            "TipoCFE": self.l10n_latam_document_type_id.code,
            "FchEmis": self.scheduled_date.date(),
            "TipoTraslado": self.l10n_uy_transfer_of_goods,  # A5
        }

        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "ModVenta": self.l10n_uy_edi_cfe_sale_mode or None,  # A14
        #         "ViaTransp": self.l10n_uy_edi_cfe_transport_route or None,  # A15
        #     })

        empty_values = {}.fromkeys([
            'MntBruto', 'FmaPago', 'FchVenc', 'ClauVenta', 'InfoAdicionalDoc', "ModVenta", "ViaTransp"
            ], None)
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_issuer(self):
        return {
            "RUCEmisor": self.company_id.vat,
            "RznSoc": self.company_id.name[:150],
            "CdgDGISucur": self.company_id.l10n_uy_edi_branch_code,
            "DomFiscal": self.company_id.partner_id._l10n_uy_edi_get_fiscal_address(),
            "Ciudad": (self.company_id.city or "")[:30] or None,
            "Departamento": (self.company_id.state_id.name or '')[:30] or None,
            "InfoAdicionalEmisor": self.l10n_uy_edi_document_id._get_legends("issuer", self) or None
        }

    def _l10n_uy_stock_cfe_A_receptor(self):
        """ XML Section A (Encabezado / Receptor) """
        self.ensure_one()
        doc_type = self.partner_id._l10n_uy_edi_get_doc_type()
        values = {
            "TipoDocRecep": doc_type or None,  # A60
            "CodPaisRecep": self.partner_id.country_id.code or ("UY" if doc_type in [2, 3] else "99"),  # A61
            "DocRecep": self.partner_id.vat if doc_type in [1, 2, 3] else None,  # A62
            "DocRecepExt": self.partner_id.vat if doc_type not in [1, 2, 3] else None,  # A62.1
            "RznSocRecep": self.partner_id.name[:150] or None,  # A63
            "DirRecep": self.partner_id._l10n_uy_edi_get_fiscal_address() or None,  # A64
            "CiudadRecep": self.partner_id.city and self.partner_id.city[:30] or None,  # A65
            "DeptoRecep": self.partner_id.state_id and self.partner_id.state_id.name[:30] or None,  # A66
            "PaisRecep": self.partner_id.country_id and self.partner_id.country_id.name or None,  # A66.1
            "InfoAdicional": self.l10n_uy_edi_document_id._get_legends("receiver", self) or None,  # A68
            "LugarDestEnt": self.l10n_uy_edi_place_of_delivery or None,  # A69
        }
        empty_values = {}.fromkeys([
            'CompraID'
            ], None)
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_totals(self):
        """ XML Section C (SUBTOTALES INFORMATIVOS) """
        self.ensure_one()
        currency_name = self.company_id.currency_id.name if self.company_id.currency_id else None
        lines = self._uy_get_cfe_lines()
        res = {
            'CantLinDet': len(lines),  # A126
        }

        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "MntExpoyAsim": sum(self.move_line_ids.mapped('quantity')) or None,
        #         "TpoMoneda": currency_name if not self.l10n_latam_document_type_id.code == '181' else None,  # A110
        #         'TpoCambio': None if currency_name == "UYU" else self._l10n_uy_edi_get_used_rate() or None,  # A111
        #     })

        empty_values = {}.fromkeys([
            "MntNoGrv", "MntNetoIvaTasaMin", "MntNetoIVATasaBasica", "IVATasaMin", "IVATasaBasica", "MntIVATasaMin", "MntIVATasaBasica", "MntTotal", "MontoNF", "MntPagar", "TpoMoneda", "TpoCambio", "MntExpoyAsim",
            ], None)
        res.update(empty_values)
        return res

    def _l10n_uy_stock_cfe_B_details(self):
        self.ensure_one()
        res = []

        # Solo Remito de Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     invoice_ind = 10  # For B4

        for k, line in enumerate(self.move_line_ids, start=1):
            temp = {
                "NroLinDet": k,  # B1
                "IndFact": None,  # B4
                "NomItem": line.display_name,  # B7
                "DscItem": line.description_picking if line.description_picking and line.description_picking != line.display_name else None,  # B8
                "Cantidad": line.quantity,  # B9
                "UniMed": line.product_uom_id.name[:4] if line.product_uom_id else "N/A",  # B10
                #"PrecioUnitario": line.price_unit,  # B11 como encuentro el precio unitario para facturas de expo ?
                #"MontoItem": line.price_total if tax_included else line.price_subtotal,  # B24 como encuentro el precio unitario para facturas de expo ?
            }
            empty_values = {}.fromkeys([
                'PrecioUnitario', 'DescuentoPct', 'DescuentoMonto', 'MontoItem',
                ], None)
            temp.update(empty_values)
            res.append(temp)

        return res

    def _l10n_uy_edi_cfe_F_reference(self):
        """ XML Section F (REFERENCE INFORMATION) """
        self.ensure_one()
        res = []
        related_docs = self.l10n_uy_edi_related_docs_ids
        for k, related_cfe in enumerate(related_docs, 1):
            cfe_serie, cfe_number = self.l10n_uy_edi_document_id._get_doc_parts(related_cfe)
            res.append({
                "NroLinRef": k,  # F1
                "TpoDocRef": int(related_cfe.l10n_latam_document_type_id.code),  # F3
                "Serie": cfe_serie,  # F4
                "NroCFERef": cfe_number,  # F5
            })
        return res

    # TODO need to re adapt

    def uy_stock_action_preview_xml(self):
        """ En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.

        Este es un nuevo boton preview que permite pre visualizar el contenido del xml en cualquier momento, incluso
        cuando la factura aun esta en estado borrador. """
        self.l10n_uy_cfe_xml = self._l10n_uy_stock_get_xml_content().encode()

    def uy_stock_action_validate_cfe(self):
        """ Check CFE XML valid files: 350: Validación de estructura de CFE

        To make the validation of the CFE and connect to uwaure we need to have a EDI document
        For that reason if we have one we delete it and create a new one with the result of
        the validation, since we are raising and the end of the method then the edi document
        is rolled back """
        self.ensure_one()

        self.l10n_uy_edi_document_id.unlink()
        edi_doc = self.env['l10n_uy_edi.document'].create({
            "picking_id": self.id,
            "uuid": self.env['l10n_uy_edi.document']._get_uuid(self),
        })
        self.l10n_uy_edi_document_id = edi_doc

        result = edi_doc._ucfe_inbox("350", {"CfeXmlOTexto": self.l10n_uy_cfe_xml})
        response = result.get("response")
        if response is not None:
            cod_rta = response.findtext(".//{*}CodRta")
            if cod_rta != "00":
                edi_doc._update_cfe_state(result)
                edi_doc.message = _("Error creating CFẸ XML") + "\n\n" + edi_doc.message
                raise UserError(_("Error creating CFẸ XML\n\n %(errors)s",
                                errors=response.findtext(".//{*}MensajeRta")))

        raise UserError(_("XML Valido"))

    # def _l10n_uy_edi_get_used_rate(self):
    #     # COPY l10n_uy_edi
    #     self.ensure_one()
    #     # We need to use abs to avoid error on Credit Notes (amount_total_signed is negative)
    #     return abs(self.amount_total_signed) / self.amount_total

    def uy_stock_action_get_uruware_cfe(self):
        """ Boton visible en la solapa DGI que permite con el dato del UUID cargar el remito creado en
        Uruware postmorten en el Odoo

        (INBOX 360 - Consulta de estado de CFE).

        Los datos que sincroniza son

            * numero de documento
            * tipo de documento
            * estado del comprobante
            - crea el EDI document
            - agregar el pdf de la factura
        """

        # Filtrar solo los e-remitos
        uy_pickings = self.filtered(
            lambda x: x.country_code == 'UY'
            and x.picking_type_code == 'outgoing'
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_edi_cfe_state not in ['accepted', 'rejected', 'received']
        )
=======
        return res

    def _l10n_uy_edi_get_addenda(self):
        """ return string with the addenda of the remito """
        addenda = self.l10n_uy_edi_document_id._get_legends("addenda", self)
        if self.origin:
            addenda += "\n\nOrigin: %s" % self.origin
        if self.note:
            addenda += "\n\n%s" % html2plaintext(self.note)
        return addenda.strip()

    def _l10n_uy_get_delivery_guide_codes(self):
        """ return list of the available document type codes for uruguayan of stock picking"""
        # self.ensure_one()
        # if self.picking_type_code != 'outgoing':
        #     return []
        return ['0', '181']

    # XML prepapre values

    def _l10n_uy_stock_prepare_req_data(self):
        """ Creating dictionary with the request to generate a DGI EDI document """
        self.ensure_one()
        edi_doc = self.l10n_uy_edi_document_id
        xml_content = self._l10n_uy_stock_get_xml_content()
        req_data = {
            "Uuid": edi_doc.uuid,
            "TipoCfe": int(self.l10n_latam_document_type_id.code),
            "HoraReq": edi_doc.request_datetime.strftime("%H%M%S"),
            "FechaReq": edi_doc.request_datetime.date().strftime("%Y%m%d"),
            "CfeXmlOTexto": xml_content}

        if addenda := self._l10n_uy_edi_get_addenda():
            req_data["Adenda"] = addenda
        return req_data

    def _uy_get_cfe_lines(self):
        self.ensure_one()
        # Cuando está validado el remito siempre usa move_line_ids
        # Usamos move_ids_without_package para Stock moves "not in package" (stock.move)
        # move_line_ids	para Operations (stock.move.line)
        # move_line_ids_without_package	para Operations "without package" (stock.move.line)
        return self.move_line_ids

    def _l10n_uy_stock_get_xml_content(self):
        """ Create the CFE xml structure and validate it
            :return: string the xml content to send to DGI """
        self.ensure_one()
        template_name = "l10n_uy_edi_stock." + self.l10n_uy_edi_document_id._get_cfe_tag(self) + "_template"
        values = {
            "cfe": self,
            "res_model": self._name,
            "IdDoc": self._l10n_uy_stock_cfe_A_iddoc(),
            "emisor": self._l10n_uy_stock_cfe_A_issuer(),
            "receptor": self._l10n_uy_stock_cfe_A_receptor(),
            "totals_detail": self._l10n_uy_stock_cfe_A_totals(),
            "item_detail": self._l10n_uy_stock_cfe_B_details(),
            "referencia_lines": self._l10n_uy_edi_cfe_F_reference(),
            "format_float": format_float,
        }
        cfe = self.env["ir.qweb"]._render(template_name, values=values)
        return etree.tostring(cleanup_xml_node(cfe)).decode()

    def _l10n_uy_stock_cfe_A_iddoc(self):
        """ XML Section A (Encabezado) """
        values = {
            "TipoCFE": self.l10n_latam_document_type_id.code,
            "FchEmis": self.scheduled_date.date(),
            "TipoTraslado": self.l10n_uy_transfer_of_goods,  # A5
        }

        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "ModVenta": self.l10n_uy_edi_cfe_sale_mode or None,  # A14
        #         "ViaTransp": self.l10n_uy_edi_cfe_transport_route or None,  # A15
        #     })

        empty_values = {}.fromkeys([
            'MntBruto', 'FmaPago', 'FchVenc', 'ClauVenta', 'InfoAdicionalDoc', "ModVenta", "ViaTransp"
            ], None)
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_issuer(self):
        return {
            "RUCEmisor": self.company_id.vat,
            "RznSoc": self.company_id.name[:150],
            "CdgDGISucur": self.company_id.l10n_uy_edi_branch_code,
            "DomFiscal": self.company_id.partner_id._l10n_uy_edi_get_fiscal_address(),
            "Ciudad": (self.company_id.city or "")[:30] or None,
            "Departamento": (self.company_id.state_id.name or '')[:30] or None,
            "InfoAdicionalEmisor": self.l10n_uy_edi_document_id._get_legends("issuer", self) or None
        }

    def _l10n_uy_stock_cfe_A_receptor(self):
        """ XML Section A (Encabezado / Receptor) """
        self.ensure_one()
        doc_type = self.partner_id._l10n_uy_edi_get_doc_type()
        values = {
            "TipoDocRecep": doc_type or None,  # A60
            "CodPaisRecep": self.partner_id.country_id.code or ("UY" if doc_type in [2, 3] else "99"),  # A61
            "DocRecep": self.partner_id.vat if doc_type in [1, 2, 3] else None,  # A62
            "DocRecepExt": self.partner_id.vat if doc_type not in [1, 2, 3] else None,  # A62.1
            "RznSocRecep": self.partner_id.name[:150] or None,  # A63
            "DirRecep": self.partner_id._l10n_uy_edi_get_fiscal_address() or None,  # A64
            "CiudadRecep": self.partner_id.city and self.partner_id.city[:30] or None,  # A65
            "DeptoRecep": self.partner_id.state_id and self.partner_id.state_id.name[:30] or None,  # A66
            "PaisRecep": self.partner_id.country_id and self.partner_id.country_id.name or None,  # A66.1
            "InfoAdicional": self.l10n_uy_edi_document_id._get_legends("receiver", self) or None,  # A68
            "LugarDestEnt": self.l10n_uy_edi_place_of_delivery or None,  # A69
        }
        empty_values = {}.fromkeys([
            'CompraID'
            ], None)
        values.update(empty_values)
        return values

    def _l10n_uy_stock_cfe_A_totals(self):
        """ XML Section C (SUBTOTALES INFORMATIVOS) """
        self.ensure_one()
        currency_name = self.company_id.currency_id.name if self.company_id.currency_id else None
        lines = self._uy_get_cfe_lines()
        res = {
            'CantLinDet': len(lines),  # A126
        }

        # Solo para Remito Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     values.update({
        #         "MntExpoyAsim": sum(self.move_line_ids.mapped('quantity')) or None,
        #         "TpoMoneda": currency_name if not self.l10n_latam_document_type_id.code == '181' else None,  # A110
        #         'TpoCambio': None if currency_name == "UYU" else self._l10n_uy_edi_get_used_rate() or None,  # A111
        #     })

        empty_values = {}.fromkeys([
            "MntNoGrv", "MntNetoIvaTasaMin", "MntNetoIVATasaBasica", "IVATasaMin", "IVATasaBasica", "MntIVATasaMin", "MntIVATasaBasica", "MntTotal", "MontoNF", "MntPagar", "TpoMoneda", "TpoCambio", "MntExpoyAsim",
            ], None)
        res.update(empty_values)
        return res

    def _l10n_uy_stock_cfe_B_details(self):
        self.ensure_one()
        res = []

        # Solo Remito de Exportacion
        # if self.l10n_uy_edi_document_id._is_uy_remito_exp():
        #     invoice_ind = 10  # For B4

        for k, line in enumerate(self.move_line_ids, start=1):
            temp = {
                "NroLinDet": k,  # B1
                "IndFact": None,  # B4
                "NomItem": line.display_name,  # B7
                "DscItem": line.description_picking if line.description_picking and line.description_picking != line.display_name else None,  # B8
                "Cantidad": line.quantity,  # B9
                "UniMed": line.product_uom_id.name[:4] if line.product_uom_id else "N/A",  # B10
                #"PrecioUnitario": line.price_unit,  # B11 como encuentro el precio unitario para facturas de expo ?
                #"MontoItem": line.price_total if tax_included else line.price_subtotal,  # B24 como encuentro el precio unitario para facturas de expo ?
            }
            empty_values = {}.fromkeys([
                'PrecioUnitario', 'DescuentoPct', 'DescuentoMonto', 'MontoItem',
                ], None)
            temp.update(empty_values)
            res.append(temp)

        return res

    def _l10n_uy_edi_cfe_F_reference(self):
        """ XML Section F (REFERENCE INFORMATION) """
        self.ensure_one()
        res = []
        related_docs = self.l10n_uy_edi_related_docs_ids
        for k, related_cfe in enumerate(related_docs, 1):
            cfe_serie, cfe_number = self.l10n_uy_edi_document_id._get_doc_parts(related_cfe)
            res.append({
                "NroLinRef": k,  # F1
                "TpoDocRef": int(related_cfe.l10n_latam_document_type_id.code),  # F3
                "Serie": cfe_serie,  # F4
                "NroCFERef": cfe_number,  # F5
            })
        return res

    # TODO need to re adapt

    def uy_stock_action_preview_xml(self):
        """ En odoo oficial solo permite descargar el preview del xml si estamos en demo mode o si ocurrio un error.

        Este es un nuevo boton preview que permite pre visualizar el contenido del xml en cualquier momento, incluso
        cuando la factura aun esta en estado borrador. """
        self.l10n_uy_cfe_xml = self._l10n_uy_stock_get_xml_content().encode()

    def uy_stock_action_validate_cfe(self):
        """ Check CFE XML valid files: 350: Validación de estructura de CFE

        To make the validation of the CFE and connect to uwaure we need to have a EDI document
        For that reason if we have one we delete it and create a new one with the result of
        the validation, since we are raising and the end of the method then the edi document
        is rolled back """
        self.ensure_one()

        self.l10n_uy_edi_document_id.unlink()
        edi_doc = self.env['l10n_uy_edi.document'].create({
            "picking_id": self.id,
            "uuid": self.env['l10n_uy_edi.document']._get_uuid(self),
        })
        self.l10n_uy_edi_document_id = edi_doc

        result = edi_doc._ucfe_inbox("350", {"CfeXmlOTexto": self.l10n_uy_cfe_xml})
        response = result.get("response")
        if response is not None:
            cod_rta = response.findtext(".//{*}CodRta")
            if cod_rta != "00":
                edi_doc._update_cfe_state(result)
                edi_doc.message = _("Error creating CFẸ XML") + "\n\n" + edi_doc.message
                raise UserError(_("Error creating CFẸ XML\n\n %(errors)s",
                                errors=response.findtext(".//{*}MensajeRta")))

        raise UserError(_("XML Valido"))

    # def _l10n_uy_edi_get_used_rate(self):
    #     # COPY l10n_uy_edi
    #     self.ensure_one()
    #     # We need to use abs to avoid error on Credit Notes (amount_total_signed is negative)
    #     return abs(self.amount_total_signed) / self.amount_total

    def uy_stock_action_get_uruware_cfe(self):
        """ Boton visible en la solapa DGI que permite con el dato del UUID cargar el remito creado en
        Uruware postmorten en el Odoo

        (INBOX 360 - Consulta de estado de CFE).

        Los datos que sincroniza son

            * numero de documento
            * tipo de documento
            * estado del comprobante
            - crea el EDI document
            - agregar el pdf de la factura
        """

        # Filtrar solo los e-remitos
        uy_pickings = self.filtered(
            lambda x: x.country_code == 'UY'
            and x.picking_type_code == 'outgoing'
            and x.l10n_latam_document_type_id
            and int(x.l10n_latam_document_type_id.code) > 0
            and x.l10n_uy_edi_cfe_state not in ['accepted', 'rejected', 'received']
        )
>>>>>>> 9725768 (temp)

    # TODO KZ buscar el metodo _l10n_cl_get_tax_amounts para ejemplos de como extraer la info de los impuestos en un picking. viene siempre de una
    # factura
