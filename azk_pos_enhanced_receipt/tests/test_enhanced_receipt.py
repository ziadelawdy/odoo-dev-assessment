from odoo.tests import tagged
from odoo.tools import BinaryBytes
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
        for marker in ('class="azk-company', 'class="azk-customer', 'class="azk-lines-table', 'NOX Trading',
                       'class="azk-sep', 'class="azk-order-info'):
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

    def test_company_vat_kept_in_enhanced_mode(self):
        """Review fix: hiding the footer company block must not drop the legal tax ID."""
        self.env.company.vat = 'EG123456789'
        self._enable(company_details='<p>No VAT written here</p>')
        html = self._render(self._sync_order([(self.product_x, 1)]))
        self.assertIn('EG123456789', html)
        self.assertEqual(html.count('EG123456789'), 1, 'printed once')

    def test_placeholder_logo_hidden(self):
        """No receipt logo and the company still on Odoo's "Your logo" placeholder: print no logo."""
        placeholder = self.env['res.company']._get_logo()
        self.config.logo = BinaryBytes(placeholder.content)
        self._enable(receipt_logo=False)
        html = self._render(self._sync_order([(self.product_x, 1)]))
        logo_block = html[html.index('name="logo"'):]
        logo_block = logo_block[:logo_block.index('</div>')]
        self.assertNotIn('<img', logo_block)

    def test_design_a_sections(self):
        self._enable()
        order = self._sync_order([(self.product_x, 1)], customer=self.customer)
        html = self._render(order)
        self.assertGreaterEqual(html.count('class="azk-sep'), 3, 'dashed separators between the sections')
        self.assertIn('class="azk-order-info', html)
        self.assertEqual(html.count(order.pos_reference), 1, 'the ticket reference is printed once, in the order block')
        self.assertNotIn('name="cashier_name"', html, 'the cashier is printed in the order block')
        self.assertIn('azk-lines-table', html)

    def test_unit_price_not_duplicated_in_table(self):
        self._enable()
        html = self._render(self._sync_order([(self.product_x, 3)]))
        self.assertNotIn('name="standard-unit-price"', html, 'the Price column carries the unit price')
