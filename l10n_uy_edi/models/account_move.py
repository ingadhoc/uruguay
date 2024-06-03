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

<<<<<<< HEAD
||||||| parent of f465607 (temp)
    def _is_dummy_dgi_validation(self):
        # If we are on testing environment and we don't have ucfe configuration we validate only locally.
        # This is useful when duplicating the production database for training purpose or others
        self.ensure_one()
        return self.company_id._uy_get_environment_type() == 'testing' and \
            not self.company_id.sudo()._is_connection_info_complete(raise_exception=False)


    def action_l10n_uy_get_uruware_inv(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,
        Nos permite extraer la info del comprobante que fue emitido desde uruware y que no esta en Odoo para asi
        quede la info de numero de documento tipo de documento estado del comprobante"""
        uy_docs = self.env['l10n_latam.document.type'].search([('country_id.code', '=', 'UY')])
        for inv in self:
            if not inv.l10n_uy_cfe_uuid:
                raise UserError(_('Necesita definir "Clave o UUID del CFE" para poder continuar'))
            if 'error' in inv.l10n_uy_cfe_state:
                raise UserError(_('No se puede obtener la factura de un comprobante con error'))
            # TODO en este momento estamos usando este 360 porque es el que tenemos pero estamos esperando respuesta de
            # soporte uruware a ver como podemos extraer mas información y poder validarla.
            response = inv.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': inv.l10n_uy_cfe_uuid})
            inv.write({
                'l10n_latam_document_number': response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe),
                'l10n_latam_document_type_id': uy_docs.filtered(lambda x: x.code == response.Resp.TipoCfe).id,
                'l10n_uy_ucfe_state': response.Resp.CodRta,
                'l10n_uy_ucfe_msg': response.Resp.MensajeRta,
            })
            inv._update_l10n_uy_cfe_state()
            # TODO Improve add logic:
            # 1. add information to the cfe xml
            # 2. cfe another data
            # 3. validation that is the same invoice

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

=======
    def _is_dummy_dgi_validation(self):
        # If we are on testing environment and we don't have ucfe configuration we validate only locally.
        # This is useful when duplicating the production database for training purpose or others
        self.ensure_one()
        return self.company_id._uy_get_environment_type() == 'testing' and \
            not self.company_id.sudo()._is_connection_info_complete(raise_exception=False)


    def action_l10n_uy_get_uruware_inv(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,
        Nos permite extraer la info del comprobante que fue emitido desde uruware y que no esta en Odoo para asi
        quede la info de numero de documento tipo de documento estado del comprobante"""
        uy_docs = self.env['l10n_latam.document.type'].search([('country_id.code', '=', 'UY')])
        for inv in self:
            if not inv.l10n_uy_cfe_uuid:
                raise UserError(_('Necesita definir "Clave o UUID del CFE" para poder continuar'))
            if inv.l10n_uy_cfe_state and 'error' in inv.l10n_uy_cfe_state:
                raise UserError(_('No se puede obtener la factura de un comprobante con error'))
            # TODO en este momento estamos usando este 360 porque es el que tenemos pero estamos esperando respuesta de
            # soporte uruware a ver como podemos extraer mas información y poder validarla.
            response = inv.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': inv.l10n_uy_cfe_uuid})
            inv.write({
                'l10n_latam_document_number': response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe),
                'l10n_latam_document_type_id': uy_docs.filtered(lambda x: x.code == response.Resp.TipoCfe).id,
                'l10n_uy_ucfe_state': response.Resp.CodRta,
                'l10n_uy_ucfe_msg': response.Resp.MensajeRta,
            })
            inv._update_l10n_uy_cfe_state()
            # TODO Improve add logic:
            # 1. add information to the cfe xml
            # 2. cfe another data
            # 3. validation that is the same invoice

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

>>>>>>> f465607 (temp)
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

<<<<<<< HEAD
||||||| parent of f465607 (temp)
    def _l10n_uy_dgi_post(self):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """

        self._l10n_uy_validate_company_data()
        for inv in self:
            now = datetime.utcnow()
            CfeXmlOTexto = inv._l10n_uy_create_cfe().get('cfe_str')
            req_data = {
                'Uuid': 'account.move-' + str(inv.id) + '_' + str(fields.Datetime.now()),  # TODO this need to be improve
                'TipoCfe': int(inv.l10n_latam_document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto}

            req_data.update(inv._l10n_uy_get_cfe_adenda())
            req_data.update(inv._l10n_uy_get_cfe_serie())
            response, transport = inv.company_id._l10n_uy_ucfe_inbox_operation('310', req_data, return_transport=1)

            inv = inv.sudo()
            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()

            # Si conseguimos un error de factura electronica directamente hacemos rollback: para que la factura de odoo
            # quede en borrador y no tengamos quede posteada y tengamos que cancelarla luego
            if 'error' in inv.l10n_uy_cfe_state:
                self.env.cr.rollback()

            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()
            inv.l10n_uy_cfe_xml = CfeXmlOTexto
            inv.l10n_uy_dgi_xml_response = transport.xml_response
            inv.l10n_uy_dgi_xml_request = transport.xml_request
            inv.l10n_uy_cfe_uuid = response.Resp.Uuid
            inv.l10n_uy_ucfe_msg = response.Resp.MensajeRta
            inv.l10n_uy_ucfe_notif = response.Resp.TipoNotificacion

            if response.Resp.CodRta not in inv._uy_invoice_already_sent():
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
            inv.l10n_latam_document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)

            # TODO this one is failing, review why
            inv.l10n_uy_cfe_file = self.env['ir.attachment'].create({
                'name': 'CFE_{}.xml'.format(inv.l10n_latam_document_number),
                'res_model': self._name, 'res_id': inv.id,
                'type': 'binary', 'datas': base64.b64encode(CfeXmlOTexto.encode())}).id

            # If the invoice has been posted automatically print and attach the legal invoice reporte to the record.
            if 'error' not in inv.l10n_uy_cfe_state:
                inv.action_l10n_uy_get_pdf()

            # TODO este viene vacio, ver cuando realmente es seteado para asi setearlo en este momento
            # Tambien tenemos ver para que sirve 'DatosQr': 'https://www.efactura.dgi.gub.uy/consultaQRPrueba/cfe?218435730016,101,A,1,18.00,17/09/2020,gKSy8dDHR0YsTy0P4cx%2bcSu4Zvo%3d',
            # self.l10n_uy_dgi_barcode = response.Resp.ImagenQr
            # TODO evaluate if this is usefull to put it in a invoice place?
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

=======
    def _l10n_uy_dgi_post(self):
        """ Implementation via web service of service 310 – Firma y envío de CFE (individual) """

        self._l10n_uy_validate_company_data()
        for inv in self:
            now = datetime.utcnow()
            CfeXmlOTexto = inv._l10n_uy_create_cfe().get('cfe_str')
            req_data = {
                'Uuid': 'account.move-' + str(inv.id),
                'TipoCfe': int(inv.l10n_latam_document_type_id.code),
                'HoraReq': now.strftime('%H%M%S'),
                'FechaReq': now.date().strftime('%Y%m%d'),
                'CfeXmlOTexto': CfeXmlOTexto}

            req_data.update(inv._l10n_uy_get_cfe_adenda())
            req_data.update(inv._l10n_uy_get_cfe_serie())
            response, transport = inv.company_id._l10n_uy_ucfe_inbox_operation('310', req_data, return_transport=1)

            inv = inv.sudo()
            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()

            # Si conseguimos un error de factura electronica directamente hacemos rollback: para que la factura de odoo
            # quede en borrador y no tengamos quede posteada y tengamos que cancelarla luego
            if 'error' in inv.l10n_uy_cfe_state:
                self.env.cr.rollback()

            inv.l10n_uy_ucfe_state = response.Resp.CodRta
            inv._update_l10n_uy_cfe_state()
            inv.l10n_uy_cfe_xml = CfeXmlOTexto
            inv.l10n_uy_dgi_xml_response = transport.xml_response
            inv.l10n_uy_dgi_xml_request = transport.xml_request
            inv.l10n_uy_cfe_uuid = response.Resp.Uuid
            inv.l10n_uy_ucfe_msg = response.Resp.MensajeRta
            inv.l10n_uy_ucfe_notif = response.Resp.TipoNotificacion

            if response.Resp.CodRta not in inv._uy_invoice_already_sent():
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
            inv.l10n_latam_document_number = response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe)

            # TODO this one is failing, review why
            inv.l10n_uy_cfe_file = self.env['ir.attachment'].create({
                'name': 'CFE_{}.xml'.format(inv.l10n_latam_document_number),
                'res_model': self._name, 'res_id': inv.id,
                'type': 'binary', 'datas': base64.b64encode(CfeXmlOTexto.encode())}).id

            # If the invoice has been posted automatically print and attach the legal invoice reporte to the record.
            if 'error' not in inv.l10n_uy_cfe_state:
                inv.action_l10n_uy_get_pdf()

            # TODO este viene vacio, ver cuando realmente es seteado para asi setearlo en este momento
            # Tambien tenemos ver para que sirve 'DatosQr': 'https://www.efactura.dgi.gub.uy/consultaQRPrueba/cfe?218435730016,101,A,1,18.00,17/09/2020,gKSy8dDHR0YsTy0P4cx%2bcSu4Zvo%3d',
            # self.l10n_uy_dgi_barcode = response.Resp.ImagenQr
            # TODO evaluate if this is usefull to put it in a invoice place?
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

>>>>>>> f465607 (temp)
    # Helpers

    def _uy_found_related_cfe(self):
        """ return the related/origin cfe of a given cfe
        Segun cambios en formatos de CFE v.24
        los cfe relacionados deben estar aceptados por DGI
        """
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
