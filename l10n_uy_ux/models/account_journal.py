from odoo import models, fields


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_uy_type = fields.Selection(selection_add=[
        ('preprinted', 'Preprinte'),
        ('contingency', 'contingency')],
        # Estos dos tipos son agregados para tener compatibilidad hacia atras
    )

    # def _l10n_uy_get_dgi_last_invoice_number(self, document_type):
    # TODO 660 - Al consultar los valores de contigencia de la instancia me aparece error, por eso usamos los
    # definidos locales en Odoo, capaz se amejor configurarlos en el ucfe?
    # Revisar si fuera del ambiente de pruebas funciona
