import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

/**
 * Warns the cashier that the CFE was not issued: what happened, in red, and the error DGI or Uruware returned.
 */
export class CfeErrorDialog extends Component {
    static template = "l10n_uy_edi_pos_ux.CfeErrorDialog";
    static components = { Dialog };
    static props = {
        title: String,
        message: String,
        error: { type: String, optional: true },
        close: Function,
    };
}
