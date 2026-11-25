from odoo import http
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class PortalAccountUy(PortalAccount):
    @http.route()
    def portal_my_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        # Without the PDF of a validated CFE there is no printable version: neither the invoice nor a proforma
        if report_type in ("html", "pdf", "text"):
            try:
                invoice_sudo = self._document_check_access("account.move", invoice_id, access_token)
            except (AccessError, MissingError):
                return request.redirect("/my")
            if invoice_sudo._l10n_uy_edi_pos_hide_printable():
                return request.redirect(invoice_sudo.get_portal_url())
        return super().portal_my_invoice_detail(
            invoice_id, access_token=access_token, report_type=report_type, download=download, **kw
        )
