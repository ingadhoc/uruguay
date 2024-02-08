# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):

    _inherit = 'account.move'

    l10n_latam_document_type_id = fields.Many2one(change_default=True)  # This is needed to be able to save default values
    # TODO KZ hacer pr a 17 o master pidiendo que hagan este fix directamtne en el modulo de l10n_latam_base

    def _post(self, soft=True):
        """ Avoid validate contingency invoices

        Esto es para evitar que puedan crear facturas de contingencia desde el Odoo, para poder soportarlo tenemos
        que integrar la lógica de manejar el CAE desde el lado de Odoo, enviar info de numero de serie, numero a usar
        etc en el xml para que sea un XML valido. Una vez que este implementado esta parte se puede ir.
        """
        uy_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and
            x.is_invoice() and
            x.journal_id.l10n_uy_type in ['electronic', 'contingency']  and
            x.l10n_uy_cfe_state not in ['accepted', 'rejected', 'received'] and
            int(x.l10n_latam_document_type_id.code) > 100)

        if uy_invoices.filtered(lambda x: x.journal_id.l10n_uy_type == 'contingency'):
            raise UserError(_(
                'Las facturas de Contingencia aun no están implementadas en el Odoo, para crear facturas'
                ' de contingencia por favor generarla directamente desde al Uruware y luego cargar en el Odoo'))

        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        pre_validated_in_uruware = uy_invoices.filtered(lambda x: x.l10n_uy_cfe_uuid and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()

        return super(AccountMove, self - pre_validated_in_uruware)._post(soft=soft)


    @api.constrains('move_type', 'journal_id')
    def _l10n_uy_check_moves_use_documents(self):
        """ Do not let to create not invoices entries in journals that use documents """
        # TODO simil to _check_moves_use_documents. integrate somehow
        not_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and x.journal_id.type in ['sale', 'purchase'] and
            x.l10n_latam_use_documents and not x.is_invoice())
        if not_invoices:
            raise ValidationError(_(
                "The selected Journal can't be used in this transaction, please select one that doesn't use documents"
                " as these are just for Invoices."))

    # TODO KZ esto era necesario en AR para eliminar facturas de proveedor, revisar si sigue siendo ver de agregar o eliminar
    # def unlink(self):
    #     """ When using documents on vendor bills the document_number is set manually by the number given from the vendor
    #     so the odoo sequence is not used. In this case we allow to delete vendor bills with document_number/name """
    #     self.filtered(lambda x: x.move_type in x.get_purchase_types() and x.state in ('draft', 'cancel') and
    #                   x.l10n_latam_use_documents).write({'name': '/'})
    #     return super().unlink()

    # TODO KZ esto lo tendriamos que mantener para nuestros clientes que tiene el nombre largo como prefijo de
    # documento. capaz lo mejor seria hacer un script para poner todo como hace Odoo. Si hacemos eso este metodo se va

    @api.depends('name')
    def _compute_l10n_latam_document_number(self):
        """En el metodo original en latam suponemos que el codigo del tipo de documento no tiene espacios.
        Y por ello conseguimos el numero haciendo el split al coseguir el primer espacio en blanco.

        En este caso los nombres de docs uruguayos a hoy en adhoc, tienen espacios. por eso necesitamos tomar otro criterio.

        Este metodo lo que hace es llamar el original y posterior corregir los documentos uruguayos para solo tomar
        realmente la ultima parte del name seria el numero en si.

        Sin este cambio, si el name es "ND e-Ticket 00000001" coloca el "e-Ticket 00000001" como numero de doc
        Con este cambio, si el name es "ND e-Ticket 00000001" coloca el "00000001" como numero de doc"""
        super(AccountMove, self)._compute_l10n_latam_document_number()
        uy_recs_with_name = self.filtered(lambda x: x.country_code == 'UY' and x.name != '/')
        for rec in uy_recs_with_name:
            name = rec.l10n_latam_document_number
            doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
            if doc_code_prefix and name:
                name = name.split(" ")[-1]
            rec.l10n_latam_document_number = name

    def action_l10n_uy_get_uruware_cfe(self):
        """ 360: Consulta de estado de CFE: estado del comprobante en DGI,

        Nos permite extraer la info del comprobante que fue emitido desde uruware
        y que no esta en Odoo para asi quede la info de numero de documento tipo
        de documento estado del comprobante.
        """
        uy_docs = self.env['l10n_latam.document.type'].search([('country_id.code', '=', 'UY')])
        for rec in self:
            if not rec.l10n_uy_cfe_uuid:
                raise UserError(_('Please return a "UUID CFE Key" in order to continue'))
            if rec.l10n_uy_cfe_state and 'error' in rec.l10n_uy_cfe_state:
                raise UserError(_('You can not obtain the invoice with errors'))
            # TODO en este momento estamos usando este 360 porque es el que tenemos pero estamos esperando respuesta de
            # soporte uruware a ver como podemos extraer mas información y poder validarla.
            response = rec.company_id._l10n_uy_ucfe_inbox_operation('360', {'Uuid': rec.l10n_uy_cfe_uuid})
            rec.write({
                'l10n_latam_document_number': response.Resp.Serie + '%07d' % int(response.Resp.NumeroCfe),
                'l10n_latam_document_type_id': uy_docs.filtered(lambda x: x.code == response.Resp.TipoCfe).id,
            })
            rec._uy_update_cfe_state(response)
            # TODO Improve add logic:
            # 1. add information to the cfe xml
            # 2. cfe another data
            # 3. validation that is the same CFE
