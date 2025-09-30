from odoo import models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    def _call_web_service_before_invoice_pdf_render(self, invoices_data):
        # EXTENDS "account"
        for invoice, invoice_data in invoices_data.items():
            if invoice.l10n_uy_edi_error:
                # Marcamos un error silencioso que bloquea el procesamiento
                # pero no muestra popup al usuario
                invoice_data["error"] = {"silent_error": True}
                invoice_data["sending_methods"] = {}
                # invoice.button_draft()
        return super()._call_web_service_before_invoice_pdf_render(invoices_data)

    def _hook_if_errors(self, errors_data, allow_raising):
        # EXTENDS "account"
        """Filtramos los errores silenciosos para evitar que se muestren al usuario y asi permitir que se actualice la pantalla
        correctamente luego de que se haya hecho button_draft en las facturas con errores."""
        non_silent_errors = {
            move: move_data
            for move, move_data in errors_data.items()
            if not move_data.get("error", {}).get("silent_error")
        }
        if non_silent_errors:
            return super()._hook_if_errors(non_silent_errors, allow_raising=allow_raising)
        return super()._hook_if_errors(errors_data, allow_raising=allow_raising)
