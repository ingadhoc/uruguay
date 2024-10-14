from odoo.tests import common


class TestL10nReportParams(common.TransactionCase):


    def setUp(self):
        super().setUp()

        lang_es = self.env['res.lang'].search([['code', '=', 'en_AR']])
        lang_en = self.env['res.lang'].search([['code', '=', 'en_US']])
        self.content = """
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
        adenda = """
        linea 1
        linea 2
        linea 3
        linea 4
        linea 5
        linea 6
        """
        self.partner_en = self.env['res.partner'].create({
            'name': 'Partner Test Adenda EN',
            'lang': lang_en.code
        })
        partner_es = self.env['res.partner'].create({
            'name': 'Partner Test Adenda ES',
            'lang': lang_es.code
        })
        self.move_2 = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'l10n_latam_document_type_id': self.env.ref('l10n_uy_account.dc_e_ticket').id,
            'partner_id': partner_es.id,
            'narration': adenda,
            'invoice_date': '2024-01-21',
            'date': '2024-01-21',
        })

    def test_reportparams_adenda(self):
        """Creamos este test para los formatos de parametros de reporte"""

        #Nos aseguramos que se imprima el reporte en formato estandar
        nombreParametros, valoresParametros = self.move_2._get_report_params()
        self.assertFalse(nombreParametros)
        self.assertFalse(valoresParametros)

        #Agregamos adenda de mas de 6 renglones
        self.move_2.narration = self.content

        self.assertEqual(self.move_2._get_report_params(), (['adenda'],['true']),
                        "El formato de parametros es incorrecto.")

        #Agregamos partner con idioma ingles, adenda y tipo de doc (al cambiar partner se borran los campos)
        self.move_2.partner_id = self.partner_en
        self.move_2.narration = self.content
        self.move_2.l10n_latam_document_type_id = self.env.ref('l10n_uy_account.dc_e_ticket').id

        self.assertEqual(self.move_2._get_report_params(), (['adenda','reporte'], ['true','ingles']),
                        "El formato de parametros es incorrecto.")

        #Cambiamos el tipo ya que el reporte en ingles no es para e-factura
        self.move_2.l10n_latam_document_type_id = self.env.ref('l10n_uy_account.dc_e_inv').id

        self.assertEqual(self.move_2._get_report_params(), (['adenda'], ['true']),
                        "El formato de parametros es incorrecto.")
