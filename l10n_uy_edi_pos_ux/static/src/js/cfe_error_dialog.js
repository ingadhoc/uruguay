import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

/**
 * Warn the cashier that DGI did not validate the invoice, and how to fix it: the customer can be edited from the
 * POS, anything else is fixed on the invoice in the backend. Then the CFE is retried from Orders.
 */
export function l10nUyCfeErrorDialog(dialog, { title, intro, error, invoiceId }) {
    const body = _t(
        "%(intro)s\n\nWhat to do:\n1. Fix what DGI rejects (below). Customer data can be edited from the POS (Customer, then Edit); anything else is fixed on the invoice in the backend.\n2. Retry it from Orders: select the order and press Retry CFE.\n\nDGI error:\n%(error)s",
        { intro, error: error || "" }
    );
    if (!invoiceId) {
        dialog.add(AlertDialog, { title, body });
        return;
    }
    dialog.add(ConfirmationDialog, {
        title,
        body,
        confirmLabel: _t("Open the invoice in the backend"),
        confirm: () => {
            window.open(`/odoo/account.move/${invoiceId}`, "_blank");
        },
        cancelLabel: _t("Close"),
        cancel: () => {},
    });
}
