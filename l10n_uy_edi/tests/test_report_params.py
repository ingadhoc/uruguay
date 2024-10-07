from odoo.tests import common


class TestL10nReportParams(common.TransactionCase):

    # Creamos este test para los formatos de parametros de reporte

    def setUp(self):

        company_uy = self.env.ref('l10n_uy_account.company_uy')
        lang_es = self.env['res.lang'].search([['code', '=', 'en_AR']])
        lang_en = self.env['res.lang'].search([['code', '=', 'en_US']])
        content = """
        Estimated Net Weight: 25.995,00 Kg
        Estimated Gross Weight: 26.774,850 Kg
        In 1 x 40 reef
        BL Nº: TBI
        SHIPPER / MANUFACTURER: C.VALE - COOPERATIVA AGROINDUSTRIAL (SIF 3300)
        AV. ARIOSVALDO BITENCOURT, 2000 CENTRO 85950000, PALOTINA - BRASIL
        MEANS OF TRANSPORTATION: Sea
        ORIGIN: Brazil
        PORT OF LOADING: Paranagua - Brazil
        PORT OF DISCHARGE: Cebu - Philippines
        SHIPMENT DATE: September, 2024
        SALE TERMS: CNF (COST AND FREIGHT) Insurance under responsibility of the buyer
        TERMS OF PAYMENT: 100% TT Against copy of original documents
        """
        adenda = self.env['l10n.uy.adenda'].create({
            'name': 'Adenda Test pruebas',
            'legend_type': 'adenda',
            'company_id': company_uy.id,
            'apply_on': 'account.move',
            'content': content
        })
        partner_en = self.env['res.partner'].create({
            'name': 'Partner Test Adenda EN',
            'lang': lang_en.code
        })
        partner_es = self.env['res.partner'].create({
            'name': 'Partner Test Adenda ES',
            'lang': lang_es.code
        })
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_uy_account.dc_e_ticket').id,
            'partner_id': partner_en.id,
            'invoice_date': '2024-01-21',
            'date': '2024-01-21',
        })
        move_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_uy_account.dc_e_ticket').id,
            'partner_id': partner_es.id,
            'invoice_date': '2024-01-21',
            'date': '2024-01-21',
        })

    def reportparams_adenda_test(self):
        import pdb
        pdb.set_trace()
        nombreParametros, valoresParametros = self.move_2._get_report_params()
        self.assertEqual(nombreParametros, ['adenda'])
        self.assertEqual(valoresParametros, ['true'])

        nombreParametros, valoresParametros = self.move._get_report_params()

        self.assertEqual(nombreParametros, ['adenda','reporte'])
        self.assertEqual(valoresParametros, ['true','ingles'])
