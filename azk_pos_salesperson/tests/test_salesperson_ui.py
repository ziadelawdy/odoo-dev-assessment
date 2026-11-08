from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common_setup_methods import setup_product_combo_items
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon


@tagged('post_install', '-at_install')
class TestSalespersonUi(TestPointOfSaleHttpCommon):
    """Assessment test cases 2-4 and the assignment rules, driven through the POS UI."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        SalePerson = cls.env['pos.sale.person']
        cls.sp_a = SalePerson.create({'name': 'Salesperson A'})
        cls.sp_b = SalePerson.create({'name': 'Salesperson B'})
        cls.sp_c = SalePerson.create({'name': 'Salesperson C'})
        cls.main_pos_config.write({
            'active_salesperson_feature': True,
            'allowed_sale_person_ids': [(6, 0, (cls.sp_a | cls.sp_b | cls.sp_c).ids)],
        })

    def _last_order(self):
        return self.env['pos.order'].search([('config_id', '=', self.main_pos_config.id)], order='id desc', limit=1)

    def _salesperson_by_product(self, order):
        return {line.product_id.name: line.salesperson_id for line in order.lines}

    def test_tc2_line_assignment(self):
        self.start_pos_tour('AzkSalespersonLineTour')
        lines = self._salesperson_by_product(self._last_order())
        self.assertEqual(lines['Whiteboard Pen'], self.sp_a)
        self.assertEqual(lines['Letter Tray'], self.sp_b)

    def test_tc3_global_overwrites(self):
        self.start_pos_tour('AzkSalespersonGlobalTour')
        order = self._last_order()
        self.assertEqual(order.salesperson_id, self.sp_c)
        self.assertEqual(set(order.lines.salesperson_id.ids), {self.sp_c.id})
        self.assertEqual(len(order.lines), 2)

    def test_tc4_no_assignment(self):
        self.start_pos_tour('AzkSalespersonNoneTour')
        order = self._last_order()
        self.assertTrue(order.lines)
        self.assertFalse(order.lines.salesperson_id)
        self.assertFalse(order.salesperson_id)

    def test_inherit_after_global(self):
        self.start_pos_tour('AzkSalespersonInheritTour')
        lines = self._salesperson_by_product(self._last_order())
        self.assertEqual(lines['Whiteboard Pen'], self.sp_b)
        self.assertEqual(lines['Letter Tray'], self.sp_a)

    def test_merge_rule(self):
        self.start_pos_tour('AzkSalespersonMergeTour')
        pens = self._last_order().lines.filtered(lambda l: l.product_id.name == 'Whiteboard Pen')
        self.assertEqual(len(pens), 2)
        qty_by_person = {line.salesperson_id: line.qty for line in pens}
        self.assertEqual(qty_by_person, {self.sp_b: 1, self.sp_a: 2})

    def test_combo_children_follow_parent(self):
        setup_product_combo_items(self)
        self.start_pos_tour('AzkSalespersonComboTour')
        order = self._last_order()
        parent = order.lines.filtered(lambda l: l.product_id.name == 'Office Combo')
        self.assertEqual(len(parent), 1)
        children = order.lines - parent
        self.assertEqual(len(children), 3)
        self.assertEqual(set(order.lines.salesperson_id.ids), {self.sp_a.id})

    def test_reload_keeps_assignment(self):
        self.start_pos_tour('AzkSalespersonReloadTour')
        lines = self._salesperson_by_product(self._last_order())
        self.assertEqual(lines['Whiteboard Pen'], self.sp_b)
        self.assertEqual(lines['Letter Tray'], self.sp_a)

    def test_hidden_when_feature_off(self):
        self.main_pos_config.active_salesperson_feature = False
        self.start_pos_tour('AzkSalespersonHiddenTour')
        self.assertFalse(self._last_order().lines.salesperson_id)
