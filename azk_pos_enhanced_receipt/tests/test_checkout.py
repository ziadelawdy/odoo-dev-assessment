"""Checkout flow: live receipt preview on the payment screen, automatic email."""
from unittest.mock import patch

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

    def test_payment_preview_keeps_scroll(self):
        """Review fix: a re-render must not jump back to the top (the totals are at the bottom)."""
        self.main_pos_config.azk_payment_receipt_preview = True
        self.start_pos_tour('AzkPaymentPreviewScrollTour')

    # ------------------------------------------------------------------
    # G3: automatic email
    # ------------------------------------------------------------------
    def _receipt_messages(self, order):
        # the receipt mail carries the receipt image (chatter logs do not)
        return self.env['mail.message'].search([
            ('model', '=', 'pos.order'), ('res_id', '=', order.id), ('attachment_ids', '!=', False),
        ])

    def _run_email_tour(self, tour, email):
        partner = self.env['res.partner'].search([('name', '=', 'APartner Full')], limit=1)
        self.assertTrue(partner)
        partner.email = email
        # no wkhtmltoimage in tests: same stub as the native feedback screen test
        with patch.object(self.env.registry['pos.order'], 'order_receipt_generate_image', return_value=b'Receipt'):
            self.start_pos_tour(tour)
        return partner

    def test_auto_email_sends(self):
        self.main_pos_config.azk_auto_email_receipt = True
        partner = self._run_email_tour('AzkAutoEmailTour', 'apartner@example.com')
        order = self._last_order()
        self.assertEqual(order.partner_id, partner)
        self.assertTrue(self._receipt_messages(order), 'the receipt mail was sent')

    def test_auto_email_off(self):
        self.main_pos_config.azk_auto_email_receipt = False
        self._run_email_tour('AzkAutoEmailOffTour', 'apartner@example.com')
        self.assertFalse(self._receipt_messages(self._last_order()))

    def test_auto_email_customer_without_email(self):
        self.main_pos_config.azk_auto_email_receipt = True
        self._run_email_tour('AzkAutoEmailOffTour', False)
        self.assertFalse(self._receipt_messages(self._last_order()))

    def test_auto_email_skips_unsynced_order(self):
        self.main_pos_config.azk_auto_email_receipt = True
        self._run_email_tour('AzkAutoEmailUnsyncedTour', 'apartner@example.com')
