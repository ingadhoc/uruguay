from odoo import _, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    def _l10n_uy_get_dgi_last_invoice_number(self, document_type):
        """ 660 Consulta Siguiente número de CFE """
        self.ensure_one()
        res = False
        # Por los momentos, esto seria solo para comprobantes regualres electronicos, no toma en cuenta los
        # de contigencia < 200
        if self.l10n_uy_type in ['electronic'] and document_type.code != '000' and int(document_type.code) < 200:
            response = self.company_id._l10n_uy_ucfe_inbox_operation('660', {'TipoCfe': document_type.code})
            # response.Resp.Serie
<<<<<<< HEAD
            if not response.Resp.NumeroCfe:
                raise UserError(_('No tiene habilitado para emitir dicho documento, por favor revisar configuración de ') + document_type.display_name)
||||||| parent of 6f2a25c (temp)
=======
            if not response.Resp.NumeroCfe:
                raise UserError(_('You are not enabled to emit this document, please check your configuration settings of ') + document_type.display_name)
>>>>>>> 6f2a25c (temp)
            res = int(response.Resp.NumeroCfe)

        # TODO Al consultar los valores de contigencia de la instancia me aparece error, por eso usamos los
        # definidos locales en Odoo, capaz se amejor configurarlos en el ucfe?
        # Revisar si fuera del ambiente de pruebas funciona

        return res
