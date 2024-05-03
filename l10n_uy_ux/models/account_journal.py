from odoo import models, fields


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_uy_type = fields.Selection(selection_add=[
        ('preprinted', 'Preprinted'),
        ('contingency', 'Contingency')],
        # Estos dos tipos son agregados para tener compatibilidad hacia atras evaluar quien los tiene, y si lo queremos borrar o no.
    )

    def _uy_get_dgi_last_invoice_number(self, document_type):
        """ 660 - Query to get next CFE number

        By the moment, this only take into account regular CFE documents (code < 200), does not take into account contingency documents

        No se usa ahora. lo usabamos en _get_last_sequence modulo oficial edi
        """
        # TODO 660 - Al consultar los valores de contigencia de la instancia me aparece error, por eso usamos los
        # definidos locales en Odoo, capaz se amejor configurarlos en el ucfe?
        # Revisar si fuera del ambiente de pruebas funciona
        self.ensure_one()
        res = False
        if self.l10n_uy_type == 'electronic' and int(document_type.code) != 0 and int(document_type.code) < 200:
            response = self.company_id._l10n_uy_ucfe_inbox_operation('660', {'TipoCfe': document_type.code})
            if not response.Resp.NumeroCfe:
                raise UserError(_('You are not enabled to issue this document, Please check your configuration settings') + document_type.display_name)
            res = int(response.Resp.NumeroCfe)
        return res
