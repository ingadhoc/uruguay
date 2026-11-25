import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(OrderPaymentValidation.prototype, {
    async finalizeValidation() {
        const wasInContingency = this.pos.session.invoice_contingency;
        const res = await super.finalizeValidation(...arguments);
        if (!wasInContingency && this.pos.session.invoice_contingency) {
            this.pos.dialog.add(AlertDialog, {
                title: _t("Contingency mode"),
                body: _t(
                    "The CFE was rejected, so the cash register entered contingency mode: it keeps selling without invoicing. Pending invoices must be generated once the issue is solved.\n\n%s",
                    this.pos.session.l10n_uy_contingency_reason || ""
                ),
            });
        }
        return res;
    },
});
