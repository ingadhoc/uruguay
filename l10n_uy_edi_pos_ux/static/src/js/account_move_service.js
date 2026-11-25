import { AccountMoveService } from "@account/services/account_move_service";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { CfeErrorDialog } from "./cfe_error_dialog";

// The invoice of a Uruguayan sale is printed with the PDF of Uruware, asked the first time it is printed.
// Without a validated CFE there is no legal PDF: the cashier gets the error instead of a proforma.
patch(AccountMoveService.prototype, {
    async downloadPdf(accountMoveId, target = "download") {
        const result = await this.orm.call("account.move", "l10n_uy_edi_pos_download_invoice", [[accountMoveId]]);
        if (result.action) {
            return this.action.doAction(result.action);
        }
        this.dialog.add(CfeErrorDialog, {
            title: _t("The invoice cannot be printed"),
            message: result.message,
            error: result.error || "",
        });
    },
});
