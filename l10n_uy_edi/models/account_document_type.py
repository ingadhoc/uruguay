from odoo import models


class AccountDocmentType(models.Model):

    _inherit = 'account.document.type'

    def get_document_sequence_vals(self, journal):
        res = super().get_document_sequence_vals(journal)

        if self.localization == 'uruguay' and (self.code != '000' and int(self.code) < 200):
            # 660 Consulta siguiente número de CFE
            data = journal.company_id._l10n_uy_get_data('660', {'TipoCfe': self.code})
            client, auth = journal.company_id._get_client()
            response = client.service.Invoke(data)
            res.update({'prefix': "%s%s" % (res.get('prefix'), response.Resp.Serie),
                        'number_next': int(response.Resp.NumeroCfe)})
        return res
