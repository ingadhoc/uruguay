import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    l10nUyShowCfeColumn() {
        return this.pos.company.country_id?.code === "UY";
    },

    l10nUyGetCfeState(order) {
        return {
            received: _t("Waiting for DGI"),
            accepted: _t("Accepted"),
            rejected: _t("Rejected"),
            error: _t("In error"),
        }[order.l10n_uy_edi_cfe_state];
    },

    l10nUyGetCfeStateClass(order) {
        return {
            received: "text-info",
            accepted: "text-success",
        }[order.l10n_uy_edi_cfe_state] || "text-danger";
    },
});
