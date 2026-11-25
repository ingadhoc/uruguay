import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { formatCurrency } from "@web/core/currency";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { CfeErrorDialog } from "./cfe_error_dialog";

patch(OrderPaymentValidation.prototype, {
    l10nUyIsUruguayan() {
        return this.pos.company.country_id?.code === "UY";
    },

    l10nUyIsIdentified(partner) {
        // The receiver data DGI asks for above the final consumer limit
        return Boolean(partner?.vat && partner.street && partner.city && partner.state_id && partner.country_id);
    },

    async askBeforeValidation() {
        const result = await super.askBeforeValidation(...arguments);
        if (result === false) {
            return false;
        }
        // Backport of the final consumer limit of Odoo 20 (l10n_uy_edi_pos): remove it when migrating this module
        const config = this.pos.config;
        if (
            this.l10nUyIsUruguayan() &&
            config.l10n_uy_final_consumer_limit &&
            this.order.priceIncl > config.l10n_uy_final_consumer_limit &&
            !this.l10nUyIsIdentified(this.order.getPartner())
        ) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Identified customer required"),
                body: _t(
                    "This sale exceeds the amount DGI allows for an unidentified customer (%(limit)s).\nSelect a customer with ID number, address, city, state and country before paying.",
                    { limit: formatCurrency(config.l10n_uy_final_consumer_limit, this.pos.currency.id) }
                ),
            });
            return false;
        }
        return result;
    },

    shouldDownloadInvoice() {
        // The PDF of Uruware is asked only when the cashier prints the invoice
        if (this.l10nUyIsUruguayan()) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },

    async finalizeValidation() {
        const result = await super.finalizeValidation(...arguments);
        if (this.l10nUyIsUruguayan() && this.order.l10n_uy_edi_error) {
            this.pos.dialog.add(CfeErrorDialog, {
                title: _t("Sale registered, but its tax receipt was not issued"),
                message: _t(
                    "The sale was registered, but its tax receipt (CFE) was not issued because of an error, so there is nothing to print. Ask your supervisor to fix the tax receipt from the backend. To do so, give them the order number: %s",
                    this.order.pos_reference
                ),
                error: this.order.l10n_uy_edi_error,
            });
        }
        return result;
    },
});
