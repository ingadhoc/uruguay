import { AccountMoveService } from "@account/services/account_move_service";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";

// Without the PDF of a validated CFE the download would render a proforma: warn instead
patch(AccountMoveService.prototype, {
    async downloadPdf(accountMoveId, target = "download") {
        const status = await this.orm.call("account.move", "l10n_uy_edi_pos_pdf_status", [[accountMoveId]]);
        if (!status.can_download) {
            this.dialog.add(AlertDialog, { title: status.title, body: status.message });
            return;
        }
        return super.downloadPdf(...arguments);
    },
});
