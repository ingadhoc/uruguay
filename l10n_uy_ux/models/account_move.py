# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, _
from odoo.exceptions import UserError


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
