from odoo.tests import tagged
from odoo.tools.image import image_data_uri

from .common import AzkEnhancedReceiptCommon


@tagged('post_install', '-at_install')
class TestEnhancedReceipt(AzkEnhancedReceiptCommon):

    def setUp(self):
        super().setUp()
        self.open_new_session()

    def test_enhanced_on_renders_layout(self):
        self._enable()
        html = self._render(self._sync_order([(self.product_x, 2), (self.product_y, 1)], customer=self.customer))
        self.assertIn('azk-company', html)
        self.assertIn('NOX Trading', html)
        self.assertIn('<b>12 Tahrir St</b>', html, 'company details are rendered as (sanitized) HTML, not escaped')
        self.assertIn('azk-customer', html)
        self.assertIn('Sara Ali', html)
        self.assertIn('5 Nile St', html)
        self.assertIn('azk-lines-table', html)
        for header in ('Product', 'Qty', 'Price', 'Total'):
            self.assertIn(f'>{header}<', html, header)
        self.assertIn(image_data_uri(self.config.receipt_logo), html)

    def test_enhanced_off_is_native(self):
        self._enable(use_customized_receipt=False)
        html = self._render(self._sync_order([(self.product_x, 1)], customer=self.customer))
        # elements, not CSS selectors (the receipt <style> always carries the rules)
        for marker in ('class="azk-company', 'class="azk-customer', 'class="azk-lines-table', 'NOX Trading'):
            self.assertNotIn(marker, html, marker)
        self.assertIn('name="standard-line"', html)
        self.assertIn('name="standard-unit-price"', html)
        self.assertIn(image_data_uri(self.config.logo), html)

    def test_customer_hidden_when_flag_off(self):
        self._enable(show_customer_details=False)
        html = self._render(self._sync_order([(self.product_x, 1)], customer=self.customer))
        self.assertNotIn('class="azk-customer', html)
        self.assertNotIn('name="partner_info"', html, 'native customer block is replaced, not duplicated')
        self.assertNotIn('Sara Ali', html)

    def test_enhanced_logo_fallback(self):
        self._enable(receipt_logo=False)
        html = self._render(self._sync_order([(self.product_x, 1)]))
        self.assertIn(image_data_uri(self.config.logo), html)

    def test_basic_receipt_table(self):
        self._enable()
        html = self._render(self._sync_order([(self.product_x, 1)]), basic_receipt=True)
        self.assertIn('azk-lines-table', html)
        self.assertIn('>Product<', html)
        self.assertIn('>Qty<', html)
        self.assertNotIn('>Price<', html)
        self.assertNotIn('>Total<', html)

    def test_no_duplicate_company_info(self):
        self._enable()
        html = self._render(self._sync_order([(self.product_x, 1)]))
        self.assertNotIn('name="company_info"', html, 'native footer company block is hidden in enhanced mode')

    def test_unit_price_not_duplicated_in_table(self):
        self._enable()
        html = self._render(self._sync_order([(self.product_x, 3)]))
        self.assertNotIn('name="standard-unit-price"', html, 'the Price column carries the unit price')
