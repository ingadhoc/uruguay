from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon
from odoo.tests import tagged

from .common import TestPosCfeErrorCommon


@tagged("-at_install", "post_install", "post_install_l10n")
class TestFinalConsumerLimitTour(AccountTestInvoicingHttpCommon, TestPosCfeErrorCommon):
    def test_final_consumer_limit_stops_the_sale(self):
        self.env["product.product"].create(
            {
                "name": "Expensive product",
                "list_price": 300000,
                "available_in_pos": True,
                "taxes_id": [(6, 0, self.tax_22.ids)],
            }
        )
        config = self._create_config()
        config.open_ui()
        self.start_tour(f"/pos/ui/{config.id}", "l10n_uy_edi_pos_ux_final_consumer_limit", login=self.env.user.login)
        self.assertFalse(config.current_session_id.order_ids.filtered(lambda o: o.state != "draft"))
