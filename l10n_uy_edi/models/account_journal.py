from odoo import models


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    def _l10n_uy_get_dgi_last_invoice_number(self, document_type):
        """ 660 Consulta Siguiente número de CFE """
        self.ensure_one()
        # Por los momentos, esto seria solo para comprobantes regualres electronicos, no toma en cuenta los
        # de contigencia < 200
        if self.l10n_uy_type in ['electronic'] and document_type.code != '000' and int(document_type.code) < 200:
            response = self.company_id._l10n_uy_ucfe_inbox_operation('660', {'TipoCfe': document_type.code})
            # response.Resp.Serie
            res = int(response.Resp.NumeroCfe)

        # TODO Al consultar los valores de contigencia de la instancia me aparece error, por eso usamos los
        # definidos locales en Odoo, capaz se amejor configurarlos en el ucfe?
        # Revisar si fuera del ambiente de pruebas funciona

        return res
