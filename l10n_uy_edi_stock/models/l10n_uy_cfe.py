from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_repr


class L10nUyCfe(models.Model):

    _inherit = 'l10n.uy.cfe'

    def _is_uy_remito_type_cfe(self):
        return self.l10n_latam_document_type_id.internal_type in ['stock_picking']

    def _uy_get_uuid(self):
        """ Extend to properly return picking info

        Uruware UUID and also A4.1 NroInterno DGI field. Spec (V24)
        Nº interno que referencia -  ALFA50 - Sin validación al comprobante
        """
        self.ensure_one()
        if self.picking_id and not self.move_id:
            res = self.picking_id._name + '-' + str(self.picking_id.id)
            if self.company_id._uy_get_environment_type() == 'testing':
                res = 'sp' + str(self.picking_id.id) + '-' + self.env.cr.dbname
            return res[:50]
        return super()._uy_get_uuid()

    def _uy_cfe_B4_IndFact(self, line):
        """ B4: Indicador de facturación

        Indica si el producto o servicio es exento, o a que tasa está gravado o si corresponde a un concepto no
        facturable.

        Extendido para remitos

        En la docu de DGI dice N/A para e-remito y e-remito de exportación, excepto:
            * usar indicador de facturación 8 si corresponde a un ítem a rebajar de otro remito ya emitido,
            * usar indicador de facturación 5 si corresponde a un ítem con valor unitario igual a cero (sólo para e-remito de exportación).

        * Donde argumento line es:
            * ser un stock.move para el caso de stock.picking

                move_ids_without_package	Stock moves not in package (stock.move)
                move_line_ids	Operations (stock.move.line)
                move_line_ids_without_package	Operations without package (stock.move.line)
        """
        # NOTE: By the moment, this is working for one VAT tax per move line. we should implement other cases.
        self.ensure_one()
        res = False
        if len(line) != 1:
            raise UserError(_('Only the Invoice Index can be calculated for each line'))

        if self._is_uy_remito_type_cfe():
            # Solo implementamos por los momentos en el N/A
            res = False

        else:
            return super()._uy_cfe_B4_IndFact()

        return {'IndFact': res} if res else {}

    def _uy_cfe_B8_DscItem(self, line):
        """ B8 Descripcion Adicional del ítem. Maximo 1000 caracteres """
        if self._is_uy_inv_type_cfe():
            return super()._uy_cfe_B8_DscItem(line)

        self.ensure_one()
        res = []
        for rec in line.l10n_uy_addenda_ids:
            res.append('{ %s }' % rec.content if rec.is_legend else rec.content)

        if self._is_uy_remito_type_cfe():
            res.append(line.description_picking)
        res = '\n'.join(res)
        self._uy_check_field_size('B8_DscItem', res, 1000)

        return {'DscItem': res} if res else {}

    def _uy_cfe_A_receptor(self):
        """ XML Section A (Encabezado) """
        self.ensure_one()
        cond_e_remito = self._is_uy_remito_type_cfe()

        if cond_e_remito and not all([self.partner_id.street, self.partner_id.city]):
            raise UserError(_('You must configure at least the address and city of the receiver to be able to send this CFE'))

        res = super()._uy_cfe_A_receptor()

        # A130 Monto Total a Pagar (NO debe ser reportado si de tipo remito)
        if self._is_uy_remito_type_cfe():
            res.pop('MntPagar')

        return res

    def _uy_cfe_C_totals(self):
        self.ensure_one()
        res = super()._uy_cfe_C_totals()

        # A110 Tipo moneda transacción: Informar para todos menos para e-Rem loc
        if self._is_uy_remito_loc():
            res.pop('TpoMoneda')

        # A124 Total Monto Total (NUM 17)
        # - Si tipo de CFE= 124 (e-remito de exportación), Valor numérico de 15 enteros y 2 decimales:
        # - sino, Valor numérico de 15 enteros y 2 decimales, ≥0 : C124 = SUM(C112:C118) + SUM(C121:C123)

        # A111 Tipo de Cambio: Informar siempre que la moneda sea diferente al peso Uruguayo y no sea e-Rem Loc
        if self._is_uy_remito_loc():
            res.pop('TpoCambio')

        return res

    def _uy_get_cfe_tag(self):
        self.ensure_one()
        if self._is_uy_remito_loc():
            return 'eRem'
        elif self._is_uy_remito_exp():
            return 'eRem_Exp'
        return super()._uy_get_cfe_tag()

    def _uy_cfe_B11_PrecioUnitario(self, line, IndFact):
        """ B11: Precio Unitario. Valor numérico de 11 enteros y 6 decimales >0, excepto:

            * Si B-C4=5, B-C11 debe ser 0
            * Si B-C4=8, B-C11 puede ser ≥0
            Donde B4 es "Indicador de facturación" (IndFact)

        Required for all the documents except for e-Delivery Guide and e-Resguardo (does not apply) """
        self.ensure_one()
        if self._is_uy_remito_exp():
            res = False
            if IndFact == 5:
                res = float_repr(0, 6)
            elif IndFact == 8:
                raise UserError(_(
                    "The use of billing indicator 8 is not implemented (Corresponds to an item to be reduced from another remittance already issued)"))
                # NOTE: In order to implement we need to return the price unit of the product, but I was not able to find a direct relations between the aml and thesml.
            else:
                res = line.quantity_done
            return {'PrecioUnitario': res} if res else {}
        return super()._uy_cfe_B11_PrecioUnitario(line, IndFact)

    def _uy_cfe_B24_MontoItem(self, line):
        """ B24: Monto Item. Valor por linea de detalle. Valor numérico de 15 enteros y 2 decimales

        - Debe ser cero cuando: C4=5
        - Calculo C24 = (B-C9 * B-C11) - B-C13 + B-C17

        Donde:
            B-C4: Indicador de Facturacion. 4 - Gravado a otra tasa/iva sobre fictos.
            B-C9: Cantidad
            B-C11 Precio unitario
            B-C13 Monto Descuento
            B-C17 Monto Recargo

        No corresponde para e-Rem pero es obligatorio para e-Rem Exp """
        self.ensure_one()
        if not self._is_uy_remito_type_cfe():
            return super()._uy_cfe_B24_MontoItem(line)

        if self._is_uy_remito_exp():
            raise UserError(_('Export e-Delivery Guide'))
        return False

    #  Helpders
