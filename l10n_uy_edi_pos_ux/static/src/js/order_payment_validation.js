import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { formatCurrency } from "@web/core/currency";
import { l10nUyCfeErrorDialog } from "./cfe_error_dialog";

patch(OrderPaymentValidation.prototype, {
    l10nUyCfeErrorFlowEnabled() {
        return this.pos.config.l10n_uy_cfe_error_flow && this.pos.config.l10n_uy_cfe_error_flow !== "native";
    },

    l10nUyIsIdentified(partner) {
        // The receiver data DGI asks for above the final consumer limit
        return Boolean(
            partner?.vat && partner.street && partner.city && partner.state_id && partner.country_id
        );
    },

    async askBeforeValidation() {
        const result = await super.askBeforeValidation(...arguments);
        if (result === false) {
            return false;
        }
        // Backport of the final consumer limit of Odoo 20 (l10n_uy_edi_pos): remove it when migrating this module
        const config = this.pos.config;
        if (
            config.l10n_uy_check_final_consumer_limit &&
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
        // Without a CFE validated by DGI there is no legal PDF: the cashier gets the error instead
        if (this.l10nUyCfeErrorFlowEnabled() && this.order.l10n_uy_edi_error) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },

    async finalizeValidation() {
        const wasInContingency = this.pos.session.invoice_contingency;
        const result = await super.finalizeValidation(...arguments);
        if (this.l10nUyCfeErrorFlowEnabled() && this.order.l10n_uy_edi_error) {
            const contingency = !wasInContingency && this.pos.session.invoice_contingency;
            const intro = contingency
                ? _t(
                      "The sale was registered, but DGI did not validate its invoice, so it has no number or PDF yet.\nThe cash register entered contingency mode: it keeps selling without invoicing. Once the problem is solved, end the contingency mode, retry this CFE and generate the pending invoices from the session."
                  )
                : _t("The sale was registered, but DGI did not validate its invoice, so it has no number or PDF yet.");
            l10nUyCfeErrorDialog(this.pos.dialog, {
                title: contingency ? _t("CFE not validated: contingency mode") : _t("CFE not validated in DGI"),
                intro,
                error: this.order.l10n_uy_edi_error,
                invoiceId: this.order.account_move?.id,
            });
        }
        return result;
    },
});
