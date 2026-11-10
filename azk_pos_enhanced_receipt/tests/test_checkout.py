"""Checkout flow: live receipt preview on the payment screen, automatic email."""
from odoo.tests import tagged
from odoo.tools import BinaryBytes

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

from .common import RECEIPT_LOGO


@tagged('post_install', '-at_install')
class TestCheckoutUi(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.main_pos_config.write({
            'use_customized_receipt': True,
            'receipt_logo': BinaryBytes(RECEIPT_LOGO),
            'company_name': '<p>NOX Trading</p>',
            'company_details': '<p>12 Tahrir St</p>',
            'show_customer_details': True,
        })

    def _last_order(self):
        return self.env['pos.order'].search([('config_id', '=', self.main_pos_config.id)], order='id desc', limit=1)

    # ------------------------------------------------------------------
    # G1: receipt preview
    # ------------------------------------------------------------------
    def test_payment_preview(self):
        self.main_pos_config.azk_payment_receipt_preview = True
        self.start_pos_tour('AzkPaymentPreviewTour')

    def test_payment_preview_native_receipt(self):
        """Customized receipt off: the preview shows the native receipt."""
        self.main_pos_config.write({'azk_payment_receipt_preview': True, 'use_customized_receipt': False})
        self.start_pos_tour('AzkPaymentPreviewNativeTour')

    def test_payment_preview_off(self):
        self.main_pos_config.azk_payment_receipt_preview = False
        self.start_pos_tour('AzkPaymentPreviewOffTour')
