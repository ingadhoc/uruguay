# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):

    _inherit = 'account.move'

    # This is needed to be able to save default values
    # TODO KZ hacer pr a 17 o master pidiendo que hagan este fix directamtne en el modulo de l10n_latam_base
    l10n_latam_document_type_id = fields.Many2one(change_default=True)

    def _l10n_uy_edi_send(self):
        """ Si queremos permitir al usuario cargar una factura de Uruwuare post mortem en Odoo.
        Para que esto funcione tenemos estas opciones

        1. hacer el campo uuid editable y stored en la factura, y que ahi pongan el valor que quieran
        2. irnos por el approach odoo que es que generen un nuevo diario manual y que lo carguen ahi
        3. approach de consuñtar el comprobamte emitido con ws y descargar la info del xml y auto popular
           como hacemos con facturas proveedor """
        # If the invoice was previosly validated in Uruware and need to be link to Odoo we check that the
        # l10n_uy_edi_cfe_uuid has been manually set and we consult to get the invoice information from Uruware
        # TODO KZ necesitamos adaptar el UUID para que pueda ser modificado
        pre_validated_in_uruware = self.filtered(lambda x: x.l10n_uy_edi_cfe_uuid and not x.l10n_uy_cfe_state)
        if pre_validated_in_uruware:
            pre_validated_in_uruware.action_l10n_uy_get_uruware_cfe()

        return super(AccountMove, self - pre_validated_in_uruware)._l10n_uy_edi_send()

    def l10n_uy_edi_action_update_dgi_state(self):
        """ Extendenmos de l10n_uy_edi solo para evitar que puedan actualizar estado de DGI
        en factura que no tengan UUID o que esten en estado error
        Nos permite extraer la info del comprobante que fue emitido desde uruware
        y que no esta en Odoo para asi quede la info de numero de documento tipo
        de documento estado del comprobante.
        """
        for rec in self:
            if not rec.l10n_uy_edi_cfe_uuid:
                raise UserError(_('Please return a "UUID CFE Key" in order to continue'))
            if rec.l10n_uy_cfe_state == 'error':
                raise UserError(_('You can not obtain the invoice with errors'))

        super().l10n_uy_edi_action_update_dgi_state()
        # TODO Improve add logic:
        # 1. add information to the cfe xml
        # 2. cfe another data
        # 3. validation that is the same CFE

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

    def action_l10n_uy_get_pdf(self):
        """ boton que permite descargar nuevamente el pdf de uruware y adjuntarlo a odoo """
        self.ensure_one()
        pdf_result = self._l10n_uy_edi_get_pdf()
        if pdf_file := pdf_result.get("pdf_file"):
            # make sure latest PDF shows to the right of the chatter
            pdf_file.register_as_main_attachment(force=True)
            self.invalidate_recordset(fnames=["invoice_pdf_report_id", "invoice_pdf_report_file"])
        if errors := pdf_result.get("errors"):
            msg = _("Error getting the PDF file: %s", errors)
            self.l10n_uy_edi_error = (self.l10n_uy_edi_error or "") + msg
            self.message_post(body=msg)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _l10n_uy_edi_get_addenda(self):
        """ Agrega el campo referencia a la adenda """
        self.ensure_one()
        res = super()._l10n_uy_edi_get_addenda()
        if self.ref:
            res += "\n\n" + _("Reference") + ": %s" % self.ref
        return res

    def l10n_uy_edi_action_update_dgi_state(self):
        """ filtrar para que solo permita usar el boton solo para facturas de clientes en
        espera de respuesta DGI """
        self.filtered(
            lambda x: x.l10n_uy_edi_cfe_state == 'received' and
            x.journal_id.type == 'sale').l10n_uy_edi_action_update_dgi_state()

    def _l10n_uy_edi_check_moves(self):
        """ valida que tanto el diario como las monedas esten bien configuradas antes de emitir
        """
        errors = super()._l10n_uy_edi_check_moves()

        uy_moves = self.filtered(lambda x: (x.company_id.country_code == 'UY' and x.l10n_latam_use_documents))
        currency_names = uy_moves.currency_id.mapped('name') + uy_moves.company_id.currency_id.mapped('name')
        if not currency_names:
            errors.append(_("You need to configure the company currency"))

        if self.journal_id.type == 'sale' and self.journal_id.l10n_uy_edi_type not in ['electronic', 'manual']:
            errors.append(_('Missing uruguayan invoicing type on journal %s.', self.name))

        return errors

