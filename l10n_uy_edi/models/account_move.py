# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _
from odoo.exceptions import UserError
import base64


class AccountMove(models.Model):

    _name = "account.move"
    _inherit = ['account.move', 'l10n.uy.cfe']

    l10n_uy_journal_type = fields.Selection(related='journal_id.l10n_uy_type')

    # This is required to be able to save defaults taking into account the document type selected
    l10n_latam_document_type_id = fields.Many2one(change_default=True)

    # Buttons

    def action_invoice_cancel(self):
        self.check_uy_state()
        return super().action_invoice_cancel()

    def _post(self, soft=True):
        """ After validate the invoices in odoo we send it to dgi via ucfe """
        res = super()._post(soft=soft)

        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and
            x.is_invoice() and
            x.journal_id.l10n_uy_type in ['electronic', 'contingency'] and
            x.l10n_uy_ucfe_state not in x._uy_cfe_already_sent() and
            # TODO possible we are missing electronic documents here, review the
            int(x.l10n_latam_document_type_id.code) > 100)

        # Esto es para evitar que puedan crear facturas de contingencia desde el Odoo, para poder soportarlo tenemos
        # que integrar la lógica de manejar el CAE desde el lado de Odoo, enviar info de numero de serie, numero a usar
        # etc en el xml para que sea un XML valido. Una vez que este implementado esta parte se puede ir.
        if uy_invoices.filtered(lambda x: x.journal_id.l10n_uy_type == 'contingency'):
            raise UserError(_('Las facturas de Contingencia aun no están implementadas en el Odoo, para crear facturas'
                              ' de contingencia por favor generarla directamente desde al Uruware y luego cargar en el'
                              ' Odoo'))

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_invoices.filtered(lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_file and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()
            uy_invoices = uy_invoices - pre_validated_in_uruware

        if not uy_invoices:
            return res

        # Send invoices to DGI and get the return info
        for inv in uy_invoices:

            # Set the invoice rate
            if inv.company_id.currency_id == inv.currency_id:
                currency_rate = 1.0
            else:
                currency_rate = inv.currency_id._convert(
                    1.0, inv.company_id.currency_id, inv.company_id, inv.date or fields.Date.today(), round=False)
            inv.l10n_uy_currency_rate = currency_rate

            if inv._is_dummy_dgi_validation():
                inv._dummy_dgi_validation()
                continue

            # TODO KZ I think we can avoid this loop. review
            inv._l10n_uy_dgi_post()

        return res

    # TODO not working review why
    # @api.onchange('journal_id', 'state')
    # def _onchange_l10n_uy_cfe_state(self):
    #     if self.state == 'draft' and not self.l10n_uy_ucfe_state:
    #         if self.l10n_uy_journal_type not in ['electronic', 'contingency']:
    #             return 'not_apply'
    #         return 'draft_cfe'
    #     return False

    def _amount_total_company_currency(self):
        """ TODO search if Odoo already have something to do exactly the same as here """
        self.ensure_one()
        return self.amount_total if self.currency_id == self.company_currency_id else self.currency_id._convert(
            self.amount_total, self.company_id.currency_id, self.company_id, self.date or fields.Date.today(), round=False)

    # Main methods

    # Helpers

<<<<<<< HEAD
    def _uy_found_related_cfe(self):
        """ return the related/origin cfe of a given cfe """
||||||| parent of 5e435b9 (temp)
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
        if self.l10n_latam_document_type_id.code in [101, 102, 103, 131, 132, 133] and len(self.invoice_line_ids) > 700:
            raise UserError('Para e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección solo puede'
                            ' reportar Hasta 700')
        # Otros CFE: Hasta 200
        elif len(self.invoice_line_ids) > 200:
            raise UserError('Para este tipo de CFE solo puede reportar hasta 200 lineas')

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        for k, line in enumerate(self.invoice_line_ids, 1):
            res.append({
                'NroLinDet': k,  # B1 No de línea o No Secuencial. a partir de 1
                'IndFact': line._l10n_uy_get_cfe_indfact(),  # B4 Indicador de facturación
                'NomItem': line.name[:80],  # B7 Nombre del ítem (producto o servicio). Maximo 80 caracteres

                'Cantidad': line.quantity,  # B9 Cantidad. NUM 17
                # TODO OJO se admite negativo? desglozar
                # TODO Valor numerico 14 enteros y 3 decimales. debemos convertir el formato a representarlo

                'UniMed': line.product_uom_id.name[:4] if line.product_uom_id else 'N/A',  # B10 Unidad de medida

                'PrecioUnitario': float_repr(line._get_price_total_and_subtotal(quantity=1)['price_subtotal'], 6),  # B11 Precio unitario
                'MontoItem': float_repr(line.price_subtotal, 2),  # B24 Monto Item
                # TODO en futuro para incluir descuentos B24=(B9*B11)–B13+B17
            })

        return res

    @api.model
    def _l10n_uy_get_min_by_unidad_indexada(self):
        return self.env.ref('l10n_uy_account.UYI').inverse_rate * 5000

    def is_expo_cfe(self):
        """ True of False in the current invoice is an exporation invoice type """
        self.ensure_one()
        return int(self.l10n_latam_document_type_id.code) in [121, 122, 123]

    def _l10n_uy_get_cfe_receptor(self):
        self.ensure_one()
        res = {}
        document_type = int(self.l10n_latam_document_type_id.code)
        cond_e_fact = document_type in [111, 112, 113, 141, 142, 143]
        min_ui = self._l10n_uy_get_min_by_unidad_indexada()
        cond_e_ticket = document_type in [101, 102, 103, 131, 132, 133] and self._amount_total_company_currency() > min_ui
        cond_e_boleta = document_type in [151, 152, 153]
        cond_e_contg = document_type in [201, 202, 203]
        cond_e_fact_expo = self.is_expo_cfe()

        if cond_e_fact or cond_e_ticket or cond_e_boleta or cond_e_contg or cond_e_fact_expo:
            # cond_e_fact: obligatorio RUC (C60= 2).
            # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E), debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).


            if not self.partner_id.l10n_latam_identification_type_id and not self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code:
                raise UserError(_('The partner of the invoice need to have a Uruguayan Identification Type'))

            tipo_doc = int(self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code)
            cod_pais = 'UY' if tipo_doc in [2, 3] else '99'

            if tipo_doc == 0:
                raise UserError(_('Debe indicar un tipo de documento Uruguayo para poder facturar a este cliente'))
            res.update({
                # TODO -Free Shop: siempre se debe identificar al receptor.
                'TipoDocRecep': tipo_doc,  # C60
                'CodPaisRecep': self.partner_id.country_id.code or cod_pais,   # C61
                'DocRecep' if tipo_doc in [1, 2, 3] else 'DocRecepExt': self.partner_id.vat,  # C62 / C62.1
            })

            if cond_e_fact_expo or cond_e_fact or cond_e_ticket:
                if not all([self.partner_id.street, self.partner_id.city, self.partner_id.state_id, self.partner_id.country_id, self.partner_id.vat]):
                    msg = _('Debe configurar la dirección, ciudad, provincia, pais del receptor y número de identificación')
                    if cond_e_ticket:
                        msg += '\n' + _('E-ticket needs these values because that total amount > 5.000 * Unidad Indexada Uruguaya') + ' (>%s)'% str(min_ui)
                    raise UserError(msg)
                res.update({
                    'RznSocRecep': self.partner_id.name,  # C63
                    'DirRecep': (self.partner_id.street + (' ' + self.partner_id.street2 if self.partner_id.street2 else ''))[:70],
                    'CiudadRecep': self.partner_id.city[:30],
                    'DeptoRecep': self.partner_id.state_id.name[:30],
                    'PaisRecep': self.partner_id.country_id.name,
                })

        return res

    def _l10n_uy_get_cfe_tag(self):
        self.ensure_one()
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code in [101, 102, 103, 201]:
            return 'eTck'
        elif cfe_code in [111, 112, 113]:
            return 'eFact'
        elif cfe_code in [121, 122, 123]:
            return 'eFact_Exp'
        else:
            raise UserError('Este Comprobante aun no ha sido implementado')

    def _l10n_uy_get_cfe_adenda(self):
        self.ensure_one()
        adenda = ''
        for rec in self.company_id.l10n_uy_adenda_ids:
            if bool(safe_eval(rec.condition, {'inv': self})) == True:
                adenda +=  "\n\n" + rec.content

        # Si el comprobante/factura tiene una referencia entonces agregarla para que se muestre al final de la Adenda
        if self.ref:
            adenda += "\n\nReferencia: %s" % self.ref

        if adenda:
            return {'Adenda': adenda.strip()}
        return {}

    def _l10n_uy_get_cfe_serie(self):
        """ Si soy ticket de contingencia usar los valores que estan definidos en el Odoo """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res

    def _l10n_uy_get_cfe_referencia(self):
        res = []
        # If is a debit/credit note cfe then we need to inform el tag referencia
        if self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note']:
            related_cfe = self._uy_found_related_invoice()
            if not related_cfe:
                raise UserError(_('Para validar una ND/NC debe informar el Documento de Origen'))
            for k, related_cfe in enumerate(self._uy_found_related_invoice(), 1):
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

    def _l10n_uy_get_cfe_iddoc(self):
        self.ensure_one()
        res = {
            'FmaPago': 1 if self.l10n_uy_payment_type == 'cash' else 2,
            'FchVenc': self.invoice_date_due.strftime('%Y-%m-%d'),
            'FchEmis': self.date.strftime('%Y-%m-%d'),
        }
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
            'RUCEmisor': stdnum.uy.rut.compact(self.company_id.vat),
            'IdDoc': self._l10n_uy_get_cfe_iddoc(),
            'item_detail': self._l10n_uy_get_cfe_item_detail(),
            'totals_detail': self._l10n_uy_get_cfe_totals(),
            'receptor': self._l10n_uy_get_cfe_receptor(),
            'cfe_tag': self._l10n_uy_get_cfe_tag(),
            'referencia_lines': self._l10n_uy_get_cfe_referencia(),
        }
        cfe = self.env.ref('l10n_uy_edi.cfe_template').render(values)
        cfe = unescape(cfe.decode('utf-8')).replace(r'&', '&amp;')
        cfe = '\n'.join([item for item in cfe.split('\n') if item.strip()])

        self._l10n_uy_vaidate_cfe(cfe)
        return {'cfe_str': cfe}

    def _l10n_uy_vaidate_cfe(self, cfe, raise_exception=False):
        # Check CFE XML valid files: 350: Validación de estructura de CFE
        response = self.company_id._l10n_uy_ucfe_inbox_operation('350', {'CfeXmlOTexto': cfe})
        if response.Resp.CodRta != '00':
            # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
            # response.Resp.MensajeRta
            if raise_exception:
                raise UserError('Error al crear el XML del CFẸ\n\n' + ucfe_errors._hint_msg(response))
            # return {'errors': str(e).split('\\n')}

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
            # TODO A-C124? Total Monto Total SUM(A121:A123)
            'MntTotal': float_repr(self.amount_total, 2),
            'CantLinDet': len(self.invoice_line_ids),  # A-C126 Lineas
            'MntPagar': float_repr(self.amount_total, 2),  # A-C130 Monto Total a Pagar
        })

        # C111 Tipo de Cambio
        if self._l10n_uy_get_currency() != 'UYU':
            res['TpoCambio'] = float_repr(self.l10n_uy_currency_rate, 3)
            if self.l10n_uy_currency_rate <= 0.0:
                raise UserError(_('Not valid Currency Rate, need to be greather that 0 in order to be accepted by DGI'))

        if self.is_expo_cfe():
            res.update({
                'MntExpoyAsim': float_repr(self.amount_total, 2),  # C113
            })

        # TODO esto se puse feo..revisar que este bien balance y amount_total
        #     if any(tax.tax_group_id.l10n_ar_vat_afip_code and tax.tax_group_id.l10n_ar_vat_afip_code not in ['0', '1', '2'] for tax in line.tax_line_id) and line[amount_field]:
        #         vat_taxable |= line
        # for vat in vat_taxable:
        #     base_imp = sum(self.invoice_line_ids.filtered(lambda x: x.tax_ids.filtered(lambda y: y.tax_group_id.l10n_ar_vat_afip_code == vat.tax_line_id.tax_group_id.l10n_ar_vat_afip_code)).mapped(amount_field))

        # TODO this need to be improved, using a different way to print the tax information
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes(self.company_id)
        self._check_uruguayan_invoices()

        amount_field = 'price_subtotal'
        tax_line_exempt = self.line_ids.filtered(lambda x: tax_vat_exempt in x.tax_ids)
        if tax_line_exempt and not self.is_expo_cfe():
            res.update({
                'MntNoGrv': float_repr(sum(tax_line_exempt.mapped(amount_field)), 2),  # A112 Total Monto - No Gravado
            })

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        tax_line_basica = self.line_ids.filtered(lambda x: tax_vat_22 in x.tax_line_id)
        if tax_line_basica:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_22 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C117 Total Monto Neto - IVA Tasa Basica
                    'MntNetoIVATasaBasica': float_repr(abs(base_imp), 2),
                    # A120 Tasa Mínima IVA TODO
                    'IVATasaBasica': 22,
                    # A-C122 Total IVA Tasa Básica? Monto del IVA Tasa Basica
                    'MntIVATasaBasica': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        tax_line_minima = self.line_ids.filtered(lambda x: tax_vat_10 in x.tax_line_id)
        if tax_line_minima:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_10 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C116 Total Monto Neto - IVA Tasa Minima
                    'MntNetoIvaTasaMin': float_repr(abs(base_imp), 2),
                    # A119 Tasa Mínima IVA TODO
                    'IVATasaMin': 10,
                    # A-C121 Total IVA Tasa Básica? Monto del IVA Tasa Minima
                    'MntIVATasaMin': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        return res

    def _uy_found_related_invoice(self):
        """ return the related/origin cfe of a given cfe """
=======
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
        if self.l10n_latam_document_type_id.code in [101, 102, 103, 131, 132, 133] and len(self.invoice_line_ids) > 700:
            raise UserError('Para e-Ticket, e-Ticket cta. Ajena y sus respectivas notas de corrección solo puede'
                            ' reportar Hasta 700')
        # Otros CFE: Hasta 200
        elif len(self.invoice_line_ids) > 200:
            raise UserError('Para este tipo de CFE solo puede reportar hasta 200 lineas')

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        for k, line in enumerate(self.invoice_line_ids, 1):
            res.append({
                'NroLinDet': k,  # B1 No de línea o No Secuencial. a partir de 1
                'IndFact': line._l10n_uy_get_cfe_indfact(),  # B4 Indicador de facturación
                'NomItem': line.name[:80],  # B7 Nombre del ítem (producto o servicio). Maximo 80 caracteres

                'Cantidad': line.quantity,  # B9 Cantidad. NUM 17
                # TODO OJO se admite negativo? desglozar
                # TODO Valor numerico 14 enteros y 3 decimales. debemos convertir el formato a representarlo

                'UniMed': line.product_uom_id.name[:4] if line.product_uom_id else 'N/A',  # B10 Unidad de medida

                'PrecioUnitario': float_repr(line._get_price_total_and_subtotal(quantity=1)['price_subtotal'], 6),  # B11 Precio unitario
                'MontoItem': float_repr(line.price_subtotal, 2),  # B24 Monto Item
                # TODO en futuro para incluir descuentos B24=(B9*B11)–B13+B17
            })

        return res

    @api.model
    def _l10n_uy_get_min_by_unidad_indexada(self):
        return self.env.ref('l10n_uy_account.UYI').inverse_rate * 5000

    def is_expo_cfe(self):
        """ True of False in the current invoice is an exporation invoice type """
        self.ensure_one()
        return int(self.l10n_latam_document_type_id.code) in [121, 122, 123]

    def _l10n_uy_get_cfe_receptor(self):
        self.ensure_one()
        res = {}
        document_type = int(self.l10n_latam_document_type_id.code)
        cond_e_fact = document_type in [111, 112, 113, 141, 142, 143]
        min_ui = self._l10n_uy_get_min_by_unidad_indexada()
        cond_e_ticket = document_type in [101, 102, 103, 131, 132, 133] and self._amount_total_company_currency() > min_ui
        cond_e_boleta = document_type in [151, 152, 153]
        cond_e_contg = document_type in [201, 202, 203]
        cond_e_fact_expo = self.is_expo_cfe()

        if cond_e_fact or cond_e_ticket or cond_e_boleta or cond_e_contg or cond_e_fact_expo:
            # cond_e_fact: obligatorio RUC (C60= 2).
            # cond_e_ticket: si monto neto ∑ (C112 a C118) > a tope establecido (ver tabla E), debe identificarse con NIE, RUC, CI, Otro, Pasaporte DNI o NIFE (C 60= 2, 3, 4, 5, 6 o 7).


            if not self.partner_id.l10n_latam_identification_type_id and not self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code:
                raise UserError(_('The partner of the invoice need to have a Uruguayan Identification Type'))

            tipo_doc = int(self.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code)
            cod_pais = 'UY' if tipo_doc in [2, 3] else '99'

            if tipo_doc == 0:
                raise UserError(_('Debe indicar un tipo de documento Uruguayo para poder facturar a este cliente'))
            res.update({
                # TODO -Free Shop: siempre se debe identificar al receptor.
                'TipoDocRecep': tipo_doc,  # C60
                'CodPaisRecep': self.partner_id.country_id.code or cod_pais,   # C61
                'DocRecep' if tipo_doc in [1, 2, 3] else 'DocRecepExt': self.partner_id.vat,  # C62 / C62.1
            })

            if cond_e_fact_expo or cond_e_fact or cond_e_ticket:
                if not all([self.partner_id.street, self.partner_id.city, self.partner_id.state_id, self.partner_id.country_id, self.partner_id.vat]):
                    msg = _('Debe configurar la dirección, ciudad, provincia, pais del receptor y número de identificación')
                    if cond_e_ticket:
                        msg += '\n' + _('E-ticket needs these values because that total amount > 5.000 * Unidad Indexada Uruguaya') + ' (>%s)'% str(min_ui)
                    raise UserError(msg)
                res.update({
                    'RznSocRecep': self.partner_id.name,  # C63
                    'DirRecep': (self.partner_id.street + (' ' + self.partner_id.street2 if self.partner_id.street2 else ''))[:70],
                    'CiudadRecep': self.partner_id.city[:30],
                    'DeptoRecep': self.partner_id.state_id.name[:30],
                    'PaisRecep': self.partner_id.country_id.name,
                })

        return res

    def _l10n_uy_get_cfe_tag(self):
        self.ensure_one()
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code in [101, 102, 103, 201]:
            return 'eTck'
        elif cfe_code in [111, 112, 113]:
            return 'eFact'
        elif cfe_code in [121, 122, 123]:
            return 'eFact_Exp'
        else:
            raise UserError('Este Comprobante aun no ha sido implementado')

    def _l10n_uy_get_cfe_adenda(self):
        self.ensure_one()
        adenda = ''
        for rec in self.company_id.l10n_uy_adenda_ids:
            if bool(safe_eval(rec.condition, {'inv': self})) == True:
                adenda +=  "\n\n" + rec.content

        # Si el comprobante/factura tiene una referencia entonces agregarla para que se muestre al final de la Adenda
        if self.ref:
            adenda += "\n\nReferencia: %s" % self.ref

        if adenda:
            return {'Adenda': adenda.strip()}
        return {}

    def _l10n_uy_get_cfe_serie(self):
        """ Si soy ticket de contingencia usar los valores que estan definidos en el Odoo """
        res = {}
        cfe_code = int(self.l10n_latam_document_type_id.code)
        if cfe_code > 200:
            res.update({
                'Serie': self.journal_id.code,
                'NumeroCfe': self.journal_id.sequence_number_next,
            })
        return res

    def _l10n_uy_get_cfe_referencia(self):
        res = []
        # If is a debit/credit note cfe then we need to inform el tag referencia
        if self.l10n_latam_document_type_id.internal_type in ['credit_note', 'debit_note']:
            related_cfe = self._uy_found_related_invoice()
            if not related_cfe:
                raise UserError(_('Para validar una ND/NC debe informar el Documento de Origen'))
            for k, related_cfe in enumerate(self._uy_found_related_invoice(), 1):
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

    def _l10n_uy_get_cfe_iddoc(self):
        self.ensure_one()
        res = {
            'FmaPago': 1 if self.l10n_uy_payment_type == 'cash' else 2,
            'FchVenc': self.invoice_date_due.strftime('%Y-%m-%d'),
            'FchEmis': self.date.strftime('%Y-%m-%d'),
        }
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
            'RUCEmisor': stdnum.uy.rut.compact(self.company_id.vat),
            'IdDoc': self._l10n_uy_get_cfe_iddoc(),
            'item_detail': self._l10n_uy_get_cfe_item_detail(),
            'totals_detail': self._l10n_uy_get_cfe_totals(),
            'receptor': self._l10n_uy_get_cfe_receptor(),
            'cfe_tag': self._l10n_uy_get_cfe_tag(),
            'referencia_lines': self._l10n_uy_get_cfe_referencia(),
        }
        cfe = self.env.ref('l10n_uy_edi.cfe_template').render(values)
        cfe = unescape(cfe.decode('utf-8')).replace(r'&', '&amp;')
        cfe = '\n'.join([item for item in cfe.split('\n') if item.strip()])

        self._l10n_uy_vaidate_cfe(cfe)
        return {'cfe_str': cfe}

    def _l10n_uy_vaidate_cfe(self, cfe, raise_exception=False):
        # Check CFE XML valid files: 350: Validación de estructura de CFE
        response = self.company_id._l10n_uy_ucfe_inbox_operation('350', {'CfeXmlOTexto': cfe})
        if response.Resp.CodRta != '00':
            # response.Resp.CodRta  30 o 31,   01, 12, 96, 99, ? ?
            # response.Resp.MensajeRta
            if raise_exception:
                raise UserError('Error al crear el XML del CFẸ\n\n' + ucfe_errors._hint_msg(response))
            # return {'errors': str(e).split('\\n')}

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
            # TODO A-C124? Total Monto Total SUM(A121:A123)
            'MntTotal': float_repr(self.amount_total, 2),
            'CantLinDet': len(self.invoice_line_ids),  # A-C126 Lineas
            'MntPagar': float_repr(self.amount_total, 2),  # A-C130 Monto Total a Pagar
        })

        # C111 Tipo de Cambio
        if self._l10n_uy_get_currency() != 'UYU':
            res['TpoCambio'] = float_repr(self.l10n_uy_currency_rate, 3)
            if self.l10n_uy_currency_rate <= 0.0:
                raise UserError(_('Not valid Currency Rate, need to be greather that 0 in order to be accepted by DGI'))

        if self.is_expo_cfe():
            res.update({
                'MntExpoyAsim': float_repr(self.amount_total, 2),  # C113
            })

        # TODO esto se puse feo..revisar que este bien balance y amount_total
        #     if any(tax.tax_group_id.l10n_ar_vat_afip_code and tax.tax_group_id.l10n_ar_vat_afip_code not in ['0', '1', '2'] for tax in line.tax_line_id) and line[amount_field]:
        #         vat_taxable |= line
        # for vat in vat_taxable:
        #     base_imp = sum(self.invoice_line_ids.filtered(lambda x: x.tax_ids.filtered(lambda y: y.tax_group_id.l10n_ar_vat_afip_code == vat.tax_line_id.tax_group_id.l10n_ar_vat_afip_code)).mapped(amount_field))

        # TODO this need to be improved, using a different way to print the tax information
        tax_vat_22, tax_vat_10, tax_vat_exempt = self.env['account.tax']._l10n_uy_get_taxes(self.company_id)
        self._check_uruguayan_invoices()

        amount_field = 'price_subtotal'
        tax_line_exempt = self.line_ids.filtered(lambda x: tax_vat_exempt in x.tax_ids)
        if tax_line_exempt and not self.is_expo_cfe():
            res.update({
                'MntNoGrv': float_repr(sum(tax_line_exempt.mapped(amount_field)), 2),  # A112 Total Monto - No Gravado
            })

        # NOTA: todos los montos a informar deben ir en la moneda del comprobante no en pesos uruguayos, es por eso que
        # usamos price_subtotal en lugar de otro campo
        tax_line_basica = self.line_ids.filtered(lambda x: tax_vat_22 in x.tax_line_id)
        if tax_line_basica:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_22 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C117 Total Monto Neto - IVA Tasa Basica
                    'MntNetoIVATasaBasica': float_repr(abs(base_imp), 2),
                    # A120 Tasa Mínima IVA TODO
                    'IVATasaBasica': 22,
                    # A-C122 Total IVA Tasa Básica? Monto del IVA Tasa Basica
                    'MntIVATasaBasica': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        tax_line_minima = self.line_ids.filtered(lambda x: tax_vat_10 in x.tax_line_id)
        if tax_line_minima:
            base_imp = sum(self.invoice_line_ids.filtered(lambda x: tax_vat_10 in x.tax_ids).mapped(amount_field))
            if not self.is_expo_cfe():  # Solo sino es Factuta de Exportacion
                res.update({
                    # A-C116 Total Monto Neto - IVA Tasa Minima
                    'MntNetoIvaTasaMin': float_repr(abs(base_imp), 2),
                    # A119 Tasa Mínima IVA TODO
                    'IVATasaMin': 10,
                    # A-C121 Total IVA Tasa Básica? Monto del IVA Tasa Minima
                    'MntIVATasaMin': float_repr(abs(tax_line_basica[amount_field]), 2),
                })

        return res

    def _uy_found_related_invoice(self):
        """ return the related/origin cfe of a given cfe
        Segun cambios en formatos de CFE v.24
        los cfe relacionados deben estar aceptados por DGI
        """
>>>>>>> 5e435b9 (temp)
        # next version review to merge this with l10n_ar_edi _found_related_invoice method
        self.ensure_one()
        res = self.env['account.move']
        if self.l10n_latam_document_type_id.internal_type == 'credit_note':
            res = self.reversed_entry_id
        elif self.l10n_latam_document_type_id.internal_type == 'debit_note':
            res = self.debit_origin_id
        if res and res.l10n_uy_cfe_state != 'accepted':
            raise UserError(_('El comprobante que estas anexando como referencia no es un comprobante valido para DGI(aceptado)'))
        return res

    def _is_uy_cfe(self):
        return bool(self.journal_id.l10n_latam_use_documents and self.company_id.country_code == "UY"
                    and self.journal_id.l10n_uy_type in ['electronic', 'contingency'])

    def check_uy_state(self):
        # TODO funcionando para facturas de clientes, ver para facturas de proveedor
        uy_sale_docs = self.filtered(lambda x: x.country_code == 'UY' and x.is_sale_document(include_receipts=True))
        super(AccountMove, uy_sale_docs).check_uy_state()

    # TODO KZ No estoy segura si esto lo necesitamos o no. capaz que no. lo agrego para mantener uniformidad, evaluar si dejarlo
    def _get_last_sequence_from_uruware(self):
        """ This method is called to return the highest number for electronic invoices, it will try to connect to Uruware
            only if it is necessary (when we are validating the invoice and need to set the document number) """
        last_number = 0 if self._is_dummy_dgi_validation() or self.l10n_latam_document_number \
            else self.journal_id._l10n_uy_get_dgi_last_invoice_number(self.l10n_latam_document_type_id)
        return "%s %08d" % (self.l10n_latam_document_type_id.doc_code_prefix, last_number)

    def _get_last_sequence(self, relaxed=False, with_prefix=None, lock=True):
        """ For uruguayan electronic invoice, if there is not sequence already then consult the last number from Uruware
        @return: string with the sequence, something like 'E-ticket 0000001"""
        res = super()._get_last_sequence(relaxed=relaxed, with_prefix=with_prefix, lock=lock)
        if self.country_code == "UY" and not res and self._is_uy_cfe() and self.l10n_latam_document_type_id:
            res = self._get_last_sequence_from_uruware()
        return res
