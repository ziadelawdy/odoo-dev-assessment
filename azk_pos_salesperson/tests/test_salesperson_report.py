from odoo.exceptions import ValidationError
from odoo.tests import new_test_user, tagged

from .common import AzkPosSalespersonCommon


@tagged('post_install', '-at_install')
class TestSalespersonReport(AzkPosSalespersonCommon):
    """Salesperson sales report: commission, per-line analysis, performance per order."""

    # ------------------------------------------------------------------
    # Task 1: commission rate
    # ------------------------------------------------------------------

    def test_commission_rate_bounds(self):
        for rate in (150, -1):
            with self.subTest(rate=rate), self.assertRaises(ValidationError):
                self.sp_a.commission_rate = rate

    def test_line_freezes_commission_rate(self):
        self.sp_a.commission_rate = 10
        self.open_new_session()
        first = self._sync_order([(self.product_x, 1, self.sp_a)])
        self.assertEqual(first.lines.azk_commission_rate, 10)
        self.sp_a.commission_rate = 20
        self.assertEqual(first.lines.azk_commission_rate, 10, 'a later rate change must not rewrite past sales')
        second = self._sync_order([(self.product_x, 1, self.sp_a)])
        self.assertEqual(second.lines.azk_commission_rate, 20)
        unassigned = self._sync_order([(self.product_x, 1, False)])
        self.assertEqual(unassigned.lines.azk_commission_rate, 0)

    # ------------------------------------------------------------------
    # Task 2: salesperson and commission on the native POS analysis
    # ------------------------------------------------------------------

    def _report_groups(self, model, orders, measures):
        self.env.flush_all()
        groups = self.env[model]._read_group(
            [('order_id', 'in', orders.ids)], ['salesperson_id'], measures)
        return {person: values for person, *values in groups}

    def test_report_lines_carry_salesperson(self):
        self.open_new_session()
        first = self._sync_order([(self.product_x, 1, self.sp_a), (self.product_y, 1, self.sp_b)])
        second = self._sync_order([(self.product_x, 1, False)])
        self.env.flush_all()
        rows = self.env['report.pos.order'].search([('order_id', 'in', (first | second).ids)])
        credited = {(row.order_id, row.product_id): row.salesperson_id for row in rows}
        self.assertEqual(credited, {
            (first, self.product_x): self.sp_a,
            (first, self.product_y): self.sp_b,
            (second, self.product_x): self.env['pos.sale.person'],
        })

    def test_report_sums_by_salesperson(self):
        self.open_new_session()
        orders = (
            self._sync_order([(self.product_x, 2, self.sp_a), (self.product_y, 1, self.sp_b)])
            | self._sync_order([(self.product_y, 3, self.sp_a), (self.product_x, 1, False)])
        )
        groups = self._report_groups('report.pos.order', orders, ['price_subtotal_excl:sum', 'product_qty:sum'])
        for person in (self.sp_a, self.sp_b, self.env['pos.sale.person']):
            lines = orders.lines.filtered(lambda l: l.salesperson_id == person)
            with self.subTest(person=person.name or 'unassigned'):
                self.assertAlmostEqual(groups[person][0], sum(lines.mapped('price_subtotal')))
                self.assertEqual(groups[person][1], sum(lines.mapped('qty')))

    def test_report_commission(self):
        self.sp_a.commission_rate = 10
        self.sp_b.commission_rate = 5
        self.open_new_session()
        orders = (
            self._sync_order([(self.product_x, 2, self.sp_a), (self.product_y, 1, self.sp_b)])
            # a refund line reduces the commission
            | self._sync_order([(self.product_x, -1, self.sp_a), (self.product_y, 1, False)])
        )
        groups = self._report_groups('report.pos.order', orders, ['azk_commission:sum'])
        # product X is 10 untaxed: A sold 2, then refunded 1 -> 10 net; B sold one Y (20)
        self.assertAlmostEqual(groups[self.sp_a][0], 1.0)
        self.assertAlmostEqual(groups[self.sp_b][0], 1.0)
        self.assertEqual(groups[self.env['pos.sale.person']][0], 0)

    # ------------------------------------------------------------------
    # Task 3: performance per (order, salesperson)
    # ------------------------------------------------------------------

    PERF = 'azk.pos.salesperson.report'

    def test_performance_one_row_per_order_and_salesperson(self):
        self.open_new_session()
        order = self._sync_order([
            (self.product_x, 1, self.sp_a), (self.product_y, 1, self.sp_a),
            (self.product_x, 1, self.sp_b), (self.product_y, 1, False),
        ])
        self.env.flush_all()
        rows = self.env[self.PERF].search([('order_id', '=', order.id)])
        self.assertEqual(len(rows), 3)
        by_person = {row.salesperson_id: row for row in rows}
        self.assertEqual(by_person[self.sp_a].line_count, 2)
        self.assertAlmostEqual(by_person[self.sp_a].amount_untaxed, 30)
        self.assertAlmostEqual(by_person[self.sp_b].amount_untaxed, 10)
        self.assertAlmostEqual(by_person[self.env['pos.sale.person']].amount_untaxed, 20)

    def test_performance_average_order_value(self):
        self.sp_a.commission_rate = 10
        self.open_new_session()
        orders = (
            self._sync_order([(self.product_x, 1, self.sp_a), (self.product_y, 1, self.sp_a)])  # A: 30
            | self._sync_order([(self.product_x, 1, self.sp_a), (self.product_y, 1, self.sp_b)])  # A: 10
        )
        groups = self._report_groups(self.PERF, orders, [
            'order_count:sum', 'amount_untaxed:sum', 'average_order_value:avg', 'product_qty:sum', 'commission:sum',
        ])
        orders_a, sales_a, average_a, qty_a, commission_a = groups[self.sp_a]
        self.assertEqual(orders_a, 2)
        self.assertAlmostEqual(sales_a, 40)
        self.assertAlmostEqual(average_a, 20)
        self.assertEqual(qty_a, 3)
        self.assertAlmostEqual(commission_a, 4)
        self.assertEqual(groups[self.sp_b][0], 1)

    def test_performance_refund_negative(self):
        self.open_new_session()
        order = self._sync_order([(self.product_x, 2, self.sp_a), (self.product_x, -1, self.sp_a)])
        groups = self._report_groups(self.PERF, order, ['amount_untaxed:sum', 'product_qty:sum'])
        self.assertAlmostEqual(groups[self.sp_a][0], 10)
        self.assertEqual(groups[self.sp_a][1], 1)

    def test_performance_company_rule(self):
        self.open_new_session()
        order = self._sync_order([(self.product_x, 1, self.sp_a)])
        self.env.flush_all()
        other_company = self.env['res.company'].create({'name': 'Other Shop Company'})
        outsider = new_test_user(
            self.env, login='azk_report_outsider', groups='point_of_sale.group_pos_user',
            company_id=other_company.id, company_ids=[(6, 0, other_company.ids)])
        insider = new_test_user(self.env, login='azk_report_insider', groups='point_of_sale.group_pos_user')
        domain = [('order_id', '=', order.id)]
        self.assertTrue(self.env[self.PERF].with_user(insider).search(domain))
        self.assertFalse(self.env[self.PERF].with_user(outsider).search(domain))

    # ------------------------------------------------------------------
    # Task 4: menus, actions, views
    # ------------------------------------------------------------------

    def test_report_actions_and_menus(self):
        reporting = self.env.ref('point_of_sale.menu_point_rep')
        manager = self.env.ref('point_of_sale.group_pos_manager')
        for xmlid, model in (
            ('azk_pos_salesperson.action_azk_sales_by_salesperson', 'report.pos.order'),
            ('azk_pos_salesperson.action_azk_salesperson_performance', 'azk.pos.salesperson.report'),
        ):
            with self.subTest(action=xmlid):
                action = self.env.ref(xmlid)
                self.assertEqual(action.res_model, model)
                self.assertEqual(action.view_mode.split(',')[0], 'pivot')
                self.assertIn('search_default_completed', action.context)
                menu = self.env['ir.ui.menu'].search([('action', '=', f'ir.actions.act_window,{action.id}')])
                self.assertEqual(menu.parent_id, reporting)
                self.assertEqual(menu.group_ids, manager)
                # every view of the action renders (pivot, graph, list, search)
                for view_type in ('pivot', 'graph', 'list', 'search'):
                    self.env[model].get_view(view_type=view_type)

    def test_native_analysis_groups_by_salesperson(self):
        arch = self.env['report.pos.order'].get_view(
            self.env.ref('point_of_sale.view_report_pos_order_search').id, 'search')['arch']
        self.assertIn("'group_by': 'salesperson_id'", arch.replace('"', "'"))

    def test_completed_filter_excludes_draft_and_cancel(self):
        for model in ('report.pos.order', 'azk.pos.salesperson.report'):
            arch = self.env[model].get_view(view_type='search')['arch']
            with self.subTest(model=model):
                self.assertIn('name="completed"', arch)
                self.assertIn("('state', 'in', ['paid', 'done'])", arch)
