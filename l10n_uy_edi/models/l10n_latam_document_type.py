from odoo import models


class L10nAccountDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    def get_document_sequence_vals(self, journal):
        res = super().get_document_sequence_vals(journal)
        if self.country_id.code == 'UY':
            if self.code != '000' and int(self.code) < 200:
                # 660 Consulta Siguiente número de CFE
                response = journal.company_id._l10n_uy_ucfe_inbox_operation('660', {'TipoCfe': self.code})
                res.update({'prefix': "%s%s" % (res.get('prefix'), response.Resp.Serie),
                            'number_next': int(response.Resp.NumeroCfe)})
            else:
                # TODO Al consultar los valores de contigencia de la instancia me aparece error, por eso usamos los
                # definidos locales en Odoo, capaz se amejor configurarlos en el ucfe?
                # Revisar si fuera del ambiente de pruebas funciona
                res.update({'prefix': "%s%s" % (res.get('prefix'), journal.code),
                            'number_next': 1})
        return res
