from odoo import api, fields, models

CFE_ERROR_FLOWS = [
    ("native", "Current: posted without number, the POS downloads a proforma"),
    ("draft", "POC 1: back to draft until DGI validates it, the payment is reconciled then"),
    ("posted_then_draft", "POC 2: posted and paid, then back to draft until DGI validates it"),
    ("no_odoo_pdf", "POC 3: posted, Odoo never renders a PDF, only the one from Uruware"),
    ("posted_no_pdf", "POC 4: posted without number or PDF until DGI validates it"),
    ("contingency", "POC 5: back to draft, and contingency mode on CAE or Uruware errors"),
]


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_uy_cfe_error_flow = fields.Selection(
        CFE_ERROR_FLOWS,
        string="Flow when the CFE fails",
        default="native",
        required=True,
        help="PoC only: what happens to the invoice of a sale when DGI does not validate its CFE.\n"
        "- Current: the invoice stays posted without number and the POS downloads a proforma (not a legal "
        "document).\n"
        "- POC 1: the invoice goes back to draft, without number or PDF. The payment is registered and it is "
        "reconciled once the CFE is validated.\n"
        "- POC 2: the invoice is posted and reconciled as usual, then it goes back to draft. It stays paid while "
        "in draft.\n"
        "- POC 3: the invoice stays posted. From the POS, Odoo never renders the PDF of a Uruguayan e-invoice, "
        "neither the invoice nor the proforma: only the PDF Uruware returns is downloaded.\n"
        "- POC 4: the invoice stays posted with the CFE in error, without number and without proforma.\n"
        "- POC 5: like POC 1, and when the error comes from the CAE (expired, no numbering left) or Uruware does "
        "not answer, the session enters contingency mode: the next sales are not invoiced until the cashier "
        "ends it, and the pending invoices are generated afterwards. Other errors (customer or product data) "
        "are fixed in the moment.\n"
        "In every POC the cashier is warned, no proforma is downloaded and the CFE can be retried from Orders.",
    )
    l10n_uy_allow_close_with_cfe_error = fields.Boolean(
        string="Close with CFE in error",
        help="Allow closing the session when some invoices are in draft because their CFE was not validated in DGI.",
    )
    # Backport of the final consumer limit of Odoo 20 (l10n_uy_edi_pos): remove it when migrating this module.
    l10n_uy_check_final_consumer_limit = fields.Boolean(
        string="Check the final consumer limit",
        help="Before paying, the POS asks for an identified customer when the sale exceeds the amount DGI allows "
        "for an unidentified one (5000 UI, converted with the rate of the indexed unit), instead of letting the "
        "CFE fail.",
    )
    l10n_uy_final_consumer_limit = fields.Monetary(
        string="Final consumer limit",
        compute="_compute_l10n_uy_final_consumer_limit",
        currency_field="currency_id",
    )
    l10n_uy_simulate_cfe_error = fields.Boolean(
        string="Simulate a DGI error",
        help="PoC only, and only with Uruware in demo mode: Uruware answers every CFE of this POS with an error, "
        "as if the CAE had expired and there were no numbering left.",
    )

    @api.depends("company_id")
    def _compute_l10n_uy_final_consumer_limit(self):
        edi_document = self.env["l10n_uy_edi.document"]
        today = fields.Date.context_today(self)
        for config in self:
            company = config.company_id
            config.l10n_uy_final_consumer_limit = (
                company.country_code == "UY" and edi_document._get_minimum_legal_amount(company, today)
            )

    @api.model
    def _l10n_uy_edi_pos_ux_demo_flows(self):
        return [
            ("PoC CFE 0 - Current", {"l10n_uy_cfe_error_flow": "native"}),
            ("PoC CFE 1 - Draft", {"l10n_uy_cfe_error_flow": "draft"}),
            (
                "PoC CFE 1 - Draft, can close",
                {"l10n_uy_cfe_error_flow": "draft", "l10n_uy_allow_close_with_cfe_error": True},
            ),
            ("PoC CFE 2 - Back to draft", {"l10n_uy_cfe_error_flow": "posted_then_draft"}),
            (
                "PoC CFE 2 - Back to draft, final consumer limit",
                {"l10n_uy_cfe_error_flow": "posted_then_draft", "l10n_uy_check_final_consumer_limit": True},
            ),
            (
                "PoC CFE 2 - Back to draft, DGI error",
                {"l10n_uy_cfe_error_flow": "posted_then_draft", "l10n_uy_simulate_cfe_error": True},
            ),
            ("PoC CFE 3 - No Odoo PDF", {"l10n_uy_cfe_error_flow": "no_odoo_pdf"}),
            (
                "PoC CFE 3 - No Odoo PDF, DGI error",
                {"l10n_uy_cfe_error_flow": "no_odoo_pdf", "l10n_uy_simulate_cfe_error": True},
            ),
            ("PoC CFE 4 - Posted without PDF", {"l10n_uy_cfe_error_flow": "posted_no_pdf"}),
            (
                "PoC CFE 5 - Contingency, DGI error",
                {"l10n_uy_cfe_error_flow": "contingency", "l10n_uy_simulate_cfe_error": True},
            ),
        ]

    @api.model
    def _l10n_uy_edi_pos_ux_create_demo(self):
        """One POS per flow and setting, so each one can be tried side by side. Only the missing ones are created."""
        company = self.env.ref("base.demo_company_uy", raise_if_not_found=False)
        journal = company and self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "sale"), ("l10n_uy_edi_type", "=", "electronic")],
            limit=1,
        )
        if not journal:
            return
        self = self.with_company(company)
        company.l10n_uy_edi_ucfe_env = "demo"
        tax = self.env["account.tax"].search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 22),
                ("l10n_uy_tax_category", "=", "vat"),
            ],
            limit=1,
        )
        product_prices = {"PoC CFE: product": 1000, "PoC CFE: expensive product": 300000}
        products = self.env["product.product"].search(
            [("name", "in", list(product_prices)), ("company_id", "=", company.id)]
        )
        missing = [name for name in product_prices if name not in products.mapped("name")]
        # Owned by the company, so the prices are in pesos and the POS does not convert them
        products |= self.env["product.product"].create(
            [
                {
                    "name": name,
                    "list_price": product_prices[name],
                    "company_id": company.id,
                    "taxes_id": [(6, 0, tax.ids)],
                    "available_in_pos": True,
                    "type": "consu",
                }
                for name in missing
            ]
        )
        existing = set(self.search([("company_id", "=", company.id)]).mapped("name"))
        for index, (name, values) in enumerate(self._l10n_uy_edi_pos_ux_demo_flows(), start=1):
            if name in existing:
                continue
            cash_journal = self.env["account.journal"].create(
                {"name": f"Cash {name}", "type": "cash", "code": f"PC{index:02d}", "company_id": company.id}
            )
            payment_method = self.env["pos.payment.method"].create(
                {"name": "Cash", "journal_id": cash_journal.id, "company_id": company.id}
            )
            self.create(
                {
                    "name": name,
                    "company_id": company.id,
                    "invoice_journal_id": journal.id,
                    "payment_method_ids": [(6, 0, payment_method.ids)],
                    **values,
                }
            )
