# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, fields, models
from odoo.tools import safe_eval


class L10nUyCfe(models.Model):

    _inherit = 'l10n.uy.cfe'

    # TODO not sure if we needed
    # company_id = fields.Many2one("res.compaany")

    # TO remove via script
    """
    l10n_uy_cfe_state = fields.Selection([
        ('not_apply', 'Not apply - Not a CFE'),
        ('draft_cfe', 'Draft CFE'),
        # UCFE error states
        ('xml_error', 'ERROR: CFE XML not valid'),
        ('connection_error', 'ERROR: Connection to UCFE'),
        ('ucfe_error', 'ERROR: Related to UCFE'),
    """

    # Campos preparacion y acuseo de recepcion/envio xml

    l10n_uy_cfe_xml = fields.Text('XML CFE', copy=False, groups="base.group_system")
    l10n_uy_dgi_xml_request = fields.Text('DGI XML Request', copy=False, readonly=True, groups="base.group_system")
    l10n_uy_dgi_xml_response = fields.Text('DGI XML Response', copy=False, readonly=True, groups="base.group_system")

    # Campos resultados almacenamiento de comprobantes emitidos

    l10n_uy_cfe_file = fields.Many2one('ir.attachment', string='CFE XML file', copy=False)
    l10n_uy_cfe_pdf = fields.Many2one('ir.attachment', string='CFE PDF Representation', copy=False)

    def _is_uy_remito_exp(self):
        return self.l10n_latam_document_type_id.code == '124'

    def _is_uy_remito_loc(self):
        return self.l10n_latam_document_type_id.code == '181'

    def _is_uy_resguardo(self):
        return self.l10n_latam_document_type_id.code in ['182', '282']

    def _uy_get_cfe_tag(self):
        """ No usado aun pero lo dejamos aca para futuro. capaz moverlo a modulo de resguardos? """
        self.ensure_one()
        if self._is_uy_resguardo():
            return 'eResg'
        return super()._uy_get_cfe_tag()

    def _uy_send_invoice_request(self):
        """ Extender para alamancer tambien los datos del xml request.
        Necesita ser testeado
        """
        self.ensure_one()
        # ORIG res = self.company_id._l10n_uy_ucfe_inbox_operation('310', self._uy_prepare_req_data())
        response, transport = super()._uy_send_invoice_request()

        self.l10n_uy_cfe_xml = response.get('CfeXmlOTexto')
        self.l10n_uy_dgi_xml_response = transport.xml_response
        self.l10n_uy_dgi_xml_request = transport.xml_request
        return response

    def _uy_get_report_params(self):
        """ En odoo ofical por defecto solo imprime el reporte standard de uruware.
        Aca lo extendemos para que haga dos cosas:

        1. Sirve para detectar si la adenda es muy grande automaticamente mandar a imprimir el reporte con adenda en hoja separada
        2. Sirve para enviar un reporte pre definido por el cliente en la configuracion de Odoo en lugar de imprimir el reporte por defecto de Uruware
        """
        # TODO: Aca tenemos un problema estamos revisando longitud de caracteres, pero en realidad debemos revisar es cantidad
        # de lineas que lleva la adenda, porque si es mayor que 6 lineas se corta
        addenda = self._uy_get_cfe_addenda()
        if addenda and len(addenda) > 799:
            report_params = [['adenda'], ['true']]
        else:
            # En caso de que el cliente eliga el reporte que quiere imprimir
            report_params = safe_eval.safe_eval(self.company_id.l10n_uy_report_params or '[]')

        extra_params = {}
        if report_params:
            nombreParametros = report_params[0]
            valoresParametros = report_params[1]
            versionPdf = 'ObtenerPdfConParametros'
            extra_params.update({
                'nombreParametros': nombreParametros,
                'valoresParametros': valoresParametros,
            })
        else:
            versionPdf = 'ObtenerPdf'

        return versionPdf, extra_params

    def action_uy_get_pdf(self):
        """ Solo permitir crear PDF cuando este aun no existe, y grabar en campo binario """
        # TODO toca poner a prueba
        self.ensure_one()
        if not self.l10n_uy_cfe_pdf:
            self.l10n_uy_cfe_pdf = self._uy_get_pdf()
        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=ir.attachment&id=" + str(self.l10n_uy_cfe_pdf.id) +
            "&filename_field=name&field=datas&download=true&name=" + self.l10n_uy_cfe_pdf.name,
            'target': 'self'
        }

    def action_uy_validate_cfe(self):
        """ Be able to validate a cfe """
        self.l10n_uy_edi_error = False
        self._uy_validate_cfe(self.sudo().l10n_uy_cfe_xml)

    def action_l10n_uy_preview_xml(self):
        """ Be able to show preview of the CFE to be send """
        self.l10n_uy_cfe_xml = self._uy_create_cfe().get('cfe_str')

    def _uy_prepare_req_data(self):
        self.ensure_one()
        req_data = super()._uy_prepare_req_data()
        req_data.update(self._l10n_uy_get_cfe_serie())
        return req_data

    def _l10n_uy_get_cfe_serie(self):
        """ Return dictionary with Serie CFE number.
        NOTE: In future need to be adapted for contigency records """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res

    def _uy_cfe_A_iddoc(self):
        res = super()._uy_cfe_A_iddoc()

        if self._is_uy_remito_type_cfe():  # A6
            res.update({'TipoTraslado': self.l10n_uy_transfer_of_goods})

        res.update(self._l10n_uy_get_cfe_serie())
        return res

    # def _uy_cfe_B24_MontoItem(self, line):
    # TODO en futuro para incluir descuentos B24 = (B9 * B11) - B13 + B17

    # TODO parece que tenemos estos tipos de contribuyente: IVA mínimo, Monotributo o Monotributo MIDES ver si cargarlos en el patner asi como la afip responsibility

    # def _uy_cfe_A41_RznSoc(self):
    # TODO company register name?

    def _uy_cfe_A_receptor(self):
        # TODO -Free Shop: siempre se debe identificar al receptor.
        # cond_e_boleta = document_type in [151, 152, 153]
        # cond_e_contg = document_type in [201, 202, 203]
        # cond_e_resguardo = self._is_uy_resguardo()
        # cond_e_fact: obligatorio RUC (C60= 2).
        # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E),
        # debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).

        res = super()._uy_cfe_A_receptor()
        if not self._is_uy_resguardo():
            res.update(self._uy_cfe_A70_CompraID())

        # A69 LugarDestEnt No debe de reportarse si es e-resguardo
        if self._is_uy_resguardo():
            res.pop('LugarDestEnt')

        # A130 Monto Total a Pagar (NO debe ser reportado si de tipo e-resguardo)
        if self._is_uy_resguardo():
            res.pop('MntPagar')

        return res

    # A130 Monto Total a Pagar (NO debe ser reportado si de tipo remito u e-resguardo)
    # if not self._is_uy_remito_type_cfe() and not self._is_uy_resguardo():
    #     res['MntPagar'] = float_repr(self.amount_total, 2)
    #     # TODO Esto toca adaptarlo cuando agreguemos retenciones y percepciones ya que representa la
    #     # "Suma de (monto total + valor de la retención/percepción + monto no facturable)

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

    # def _uy_cfe_A5_FchEmis(self):
    #     """ A5 FchEmis. Fecha del Comprobante """
    # return self.scheduled_date.strftime('%Y-%m-%d')
    # TODO KZ ver que fecha deberiamos de usar en caso de ser picking. opciones
    #   scheduled_date - Scheduled Date
    #   date - Creation Date
    #   date_deadline - Deadline
    #   date_done - Date of Transfer

    # def _uy_check_uy_invoices(self):
    # We check that there is one and only one vat tax per line
    # TODO KZ this could change soon, waiting functional confirmation

    # All for addendas

    def _uy_get_legends(self, tipo_leyenda, record):
        """ This method check and return the legendas configured by default that applies to the
        current CFE.
        Return type: list """
        res = []
        recordtype = {'account.move': 'inv', 'stock.picking': 'picking', 'account.move.line': 'aml', 'product.product': 'product'}
        context = {recordtype.get(record._name): record}
        for rec in record.company_id.l10n_uy_addenda_ids.filtered(lambda x: x.type == tipo_leyenda and x.apply_on in ['all', self._name]):
            if bool(safe_eval.safe_eval(rec.condition, context)):
                res.append(rec.content)
        return res

    def action_l10n_uy_mandatory_legend(self):
        self.ensure_one()
        addenda = self._uy_get_cfe_addenda()
        A16_InfoAdicionalDoc = self._uy_cfe_A16_InfoAdicionalDoc().get('InfoAdicionalDoc')
        A51_InfoAdicionalEmisor = self._uy_cfe_A51_InfoAdicionalEmisor().get('InfoAdicionalEmisor')
        A68_InfoAdicionalReceptor = self._uy_cfe_A68_InfoAdicional().get('InfoAdicional')
        B8_DscItem = []
        lines = self._uy_get_cfe_lines()
        for line in lines:
            value = self._uy_cfe_B8_DscItem(line).get('DscItem')
            if value:
                B8_DscItem.append((line.display_name, value))

        messge = "* Adenda\n%s\n\n* Info Adicional Doc\n%s\n\n* Info Adicional Emisor\n%s\n\n* Info Adicional Receptor\n%s\n\n * Info Adicional Items\n%s" % (
            addenda, A16_InfoAdicionalDoc, A51_InfoAdicionalEmisor, A68_InfoAdicionalReceptor, '\n'.join(str(item) for item in B8_DscItem))

        raise UserError(messge)

    def action_l10n_uy_addenda_preview(self):
        self.ensure_one()
        raise UserError(self._uy_get_cfe_addenda())

    def action_l10n_uy_remkark_default(self):
        self.ensure_one()
        res = self.env['l10n.uy.addenda']

        res |= self._uy_get_legends_recs('addenda', self)
        res |= self._uy_get_legends_recs('cfe_doc', self)
        res |= self._uy_get_legends_recs('emisor', self)
        res |= self._uy_get_legends_recs('receiver', self)

        for line in self._uy_get_cfe_lines():
            res |= self._uy_get_legends_recs('item', line)

        self.l10n_uy_addenda_ids = res

    def _uy_get_legends_recs(self, tipo_leyenda, record):
        """ copy of  _uy_get_legends but return browseables """
        res = self.env['l10n.uy.addenda']
        recordtype = {'account.move': 'inv', 'stock.picking': 'picking', 'account.move.line': 'aml', 'product.product': 'product'}
        context = {recordtype.get(record._name): record}
        for rec in record.company_id.l10n_uy_addenda_ids.filtered(lambda x: x.type == tipo_leyenda and x.apply_on in ['all', self._name]):
            if bool(safe_eval.safe_eval(rec.condition, context)):
                res |= rec
        return res

    @api.model
    def is_zona_franca(self):
        """ NOTE: Need to improve the way to identify the fiscal position
        """
        return bool(self.fiscal_position_id and 'zona franca' in self.fiscal_position_id.name.lower())

    def _uy_cfe_A70_CompraID(self):
        """ Número que identifica la compra: número de pedido, número orden de compra etc. LEN(50)
        Opcional para todos los tipos de documentos """
        self.ensure_one()
        res = False
        if not self._is_uy_resguardo():
            if 'purchase_order_number' in 'purchase_order_number' in self.env['account.move'].fields_get():
                res = (self.purchase_order_number or '')[:50]
        return {'CompraID': res} if res else {}

    # def _uy_cfe_F_referencia(self):
    #     # Not sure if FechaCFEref': 2015-01-31, shuould be inform
