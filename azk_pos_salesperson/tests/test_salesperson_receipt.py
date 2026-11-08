from odoo.tests import tagged

from .common import AzkPosSalespersonCommon


@tagged('post_install', '-at_install')
class TestSalespersonReceipt(AzkPosSalespersonCommon):

    def setUp(self):
        super().setUp()
        self.open_new_session()

    @staticmethod
    def _render(order):
        return str(order.order_receipt_generate_html())

    def test_receipt_data_has_salesperson_name(self):
        order = self._sync_order([(self.product_x, 1, self.sp_a), (self.product_y, 1, False)])
        data = order.order_receipt_generate_data()
        names = {line['product_data']['display_name']: line['salesperson_name'] for line in data['lines']}
        self.assertEqual(names['Product X'], 'Salesperson A')
        self.assertFalse(names['Product Y'])
        self.assertTrue(data['conditions']['azk_salesperson'])

    def test_receipt_prints_name_when_active(self):
        order = self._sync_order([(self.product_x, 1, self.sp_a)])
        html = self._render(order)
        self.assertIn('azk-salesperson', html)
        self.assertIn('Salesperson A', html)
        self.assertLess(html.index('Product X'), html.index('Salesperson A'), 'name is printed under the product')

    def test_receipt_hides_name_when_feature_off(self):
        order = self._sync_order([(self.product_x, 1, self.sp_a)])
        self.config.active_salesperson_feature = False
        html = self._render(order)
        self.assertNotIn('azk-salesperson', html)
        self.assertNotIn('Salesperson A', html)

    def test_receipt_no_name_when_unassigned(self):
        order = self._sync_order([(self.product_x, 1, False)])
        self.assertNotIn('azk-salesperson', self._render(order))
