# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):

    _inherit = 'account.move'

    def _post(self, soft=True):
        """ Avoid validate contingency invoices

       Esto es para evitar que puedan crear facturas de contingencia desde el Odoo, para poder soportarlo tenemos
       que integrar la lógica de manejar el CAE desde el lado de Odoo, enviar info de numero de serie, numero a usar
       etc en el xml para que sea un XML valido. Una vez que este implementado esta parte se puede ir.
        """
        contigency_uy_invoices = self.filtered(
            lambda x: x.company_id.country_id.code == 'UY' and
            x.is_invoice() and
            x.journal_id.l10n_uy_type == 'contingency' and
            x.l10n_uy_cfe_state not in ['accepted', 'rejected', 'received'] and
            int(x.l10n_latam_document_type_id.code) > 100)

        if contigency_uy_invoices:
            raise UserError(_(
                'Las facturas de Contingencia aun no están implementadas en el Odoo, para crear facturas'
                ' de contingencia por favor generarla directamente desde al Uruware y luego cargar en el Odoo'))

        return super()._post(soft=soft)

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
