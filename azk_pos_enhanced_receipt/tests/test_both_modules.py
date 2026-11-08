"""Both modules installed together (salesperson + enhanced receipt).

Skipped when azk_pos_salesperson is not installed.
"""
import unittest

from odoo.tests import tagged
from odoo.tools import BinaryBytes

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

from .common import AzkEnhancedReceiptCommon, RECEIPT_LOGO


def _salesperson_installed(env):
    return 'pos.sale.person' in env


@tagged('post_install', '-at_install')
class TestBothModulesReceipt(AzkEnhancedReceiptCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _salesperson_installed(cls.env):
            raise unittest.SkipTest('azk_pos_salesperson is not installed')
        cls.sp_a = cls.env['pos.sale.person'].create({'name': 'Salesperson A'})
        cls.config.write({
            'active_salesperson_feature': True,
            'allowed_sale_person_ids': [(6, 0, cls.sp_a.ids)],
        })

    def test_salesperson_inside_enhanced_table(self):
        self.open_new_session()
        self._enable()
        order = self._sync_order([(self.product_x, 1)], line_extra={'salesperson_id': self.sp_a.id})
        html = self._render(order)
        table = html[html.index('class="azk-lines-table'):]
        table = table[:table.index('</table>')]
        self.assertEqual(table.count('Salesperson: '), 1)
        self.assertIn('Salesperson A', table)
        self.assertEqual(html.count('Salesperson A'), 1, 'printed once, inside the table')


@tagged('post_install', '-at_install')
class TestBothModulesUi(TestPointOfSaleHttpCommon):
    """Assessment test cases 1 (four configurations) and 5 (config changed during a session)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _salesperson_installed(cls.env):
            raise unittest.SkipTest('azk_pos_salesperson is not installed')
        SalePerson = cls.env['pos.sale.person']
        cls.sp_a = SalePerson.create({'name': 'Salesperson A'})
        cls.sp_b = SalePerson.create({'name': 'Salesperson B'})
        cls.receipt_values = {
            'receipt_logo': BinaryBytes(RECEIPT_LOGO),
            'company_name': '<p>NOX Trading</p>',
            'company_details': '<p>12 Tahrir St</p>',
            'show_customer_details': True,
        }

    def _configure(self, name, salesperson, enhanced):
        self.main_pos_config.write({
            'name': name,
            'active_salesperson_feature': salesperson,
            'allowed_sale_person_ids': [(6, 0, (self.sp_a | self.sp_b).ids)],
            'use_customized_receipt': enhanced,
            **self.receipt_values,
        })

    def _last_order(self):
        return self.env['pos.order'].search([('config_id', '=', self.main_pos_config.id)], order='id desc', limit=1)

    def test_tc1_sales_enabled_enhanced_receipt(self):
        self._configure('POS_Sales_Enabled_Enhanced_Receipt', True, True)
        self.start_pos_tour('AzkTc1EnabledEnhancedTour')
        self.assertEqual(self._last_order().lines.salesperson_id, self.sp_a)

    def test_tc1_sales_disabled_enhanced_receipt(self):
        self._configure('POS_Sales_Disabled_Enhanced_Receipt', False, True)
        self.start_pos_tour('AzkTc1DisabledEnhancedTour')
        self.assertFalse(self._last_order().lines.salesperson_id)

    def test_tc1_sales_enabled_default_receipt(self):
        self._configure('POS_Sales_Enabled_Default_Receipt', True, False)
        self.start_pos_tour('AzkTc1EnabledDefaultTour')
        self.assertEqual(self._last_order().lines.salesperson_id, self.sp_a)

    def test_tc1_all_disabled(self):
        # values are set on purpose: they must be ignored
        self._configure('POS_All_Disabled', False, False)
        self.start_pos_tour('AzkTc1AllDisabledTour')
        self.assertFalse(self._last_order().lines.salesperson_id)

    def test_tc5_config_change_needs_reload(self):
        self._configure('POS_All_Disabled', False, False)
        self.start_pos_tour('AzkTc5ConfigChangeTour')
        config = self.main_pos_config
        self.assertTrue(config.active_salesperson_feature, 'the backend change was saved during the session')
        self.assertTrue(config.use_customized_receipt)
        self.assertFalse(self._last_order().lines.salesperson_id)
