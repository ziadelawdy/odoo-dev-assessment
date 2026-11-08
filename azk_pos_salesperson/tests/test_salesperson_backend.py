from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from .common import AzkPosSalespersonCommon


@tagged('post_install', '-at_install')
class TestSalespersonBackend(AzkPosSalespersonCommon):

    def _loaded_salespersons(self):
        session = self.open_new_session()
        data = session.load_data({'only_records': True})
        return {record['id'] for record in data.get('pos.sale.person', [])}

    @mute_logger('odoo.sql_db')
    def test_name_required(self):
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env['pos.sale.person'].create({'phone_number': '123'})

    def test_load_only_allowed_when_active(self):
        self.assertEqual(self._loaded_salespersons(), {self.sp_a.id, self.sp_b.id})

    def test_load_nothing_when_feature_off(self):
        self.config.active_salesperson_feature = False
        self.assertEqual(self._loaded_salespersons(), set())

    def test_order_line_load_fields(self):
        self.assertIn('salesperson_id', self.env['pos.order.line']._load_pos_data_fields(self.config))

    def test_sync_stores_salespersons(self):
        self.open_new_session()
        order = self._sync_order(
            [(self.product_x, 1, self.sp_a), (self.product_y, 1, self.sp_b)],
            order_vals={'salesperson_id': self.sp_a.id},
        )
        self.assertEqual(order.salesperson_id, self.sp_a)
        by_product = {line.product_id: line.salesperson_id for line in order.lines}
        self.assertEqual(by_product[self.product_x], self.sp_a)
        self.assertEqual(by_product[self.product_y], self.sp_b)

    def test_sync_without_salesperson(self):
        self.open_new_session()
        order = self._sync_order([(self.product_x, 1, False), (self.product_y, 2, False)])
        self.assertFalse(order.salesperson_id)
        self.assertFalse(order.lines.salesperson_id)

    def test_access_rights(self):
        pos_user = new_test_user(self.env, login='azk_pos_user', groups='point_of_sale.group_pos_user')
        pos_manager = new_test_user(self.env, login='azk_pos_manager', groups='point_of_sale.group_pos_manager')
        SalePerson = self.env['pos.sale.person']
        self.assertEqual(SalePerson.with_user(pos_user).browse(self.sp_a.id).name, 'Salesperson A')
        with self.assertRaises(AccessError):
            SalePerson.with_user(pos_user).create({'name': 'Not allowed'})
        self.assertTrue(SalePerson.with_user(pos_manager).create({'name': 'Allowed'}))

    def test_backend_views_show_salesperson(self):
        # Both backend list views of pos.order.line (default "All sales lines" and "Sale line")
        for xmlid in ('point_of_sale.view_pos_order_tree_all_sales_lines', 'point_of_sale.view_pos_order_line'):
            view = self.env.ref(xmlid)
            line_list = self.env['pos.order.line'].get_views([(view.id, 'list')])['views']['list']['arch']
            self.assertIn('salesperson_id', line_list, xmlid)
        order_form = self.env['pos.order'].get_views([(False, 'form')])['views']['form']['arch']
        self.assertIn('salesperson_id', order_form)
        config_form = self.env['pos.config'].get_views([(False, 'form')])['views']['form']['arch']
        settings_form = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        for field in ('active_salesperson_feature', 'allowed_sale_person_ids'):
            self.assertIn(field, config_form)
            self.assertIn(f'pos_{field}', settings_form)
        person_views = self.env['pos.sale.person'].get_views([(False, 'list'), (False, 'form'), (False, 'search')])['views']
        for field in ('name', 'phone_number', 'employee_id'):
            self.assertIn(field, person_views['form']['arch'])
