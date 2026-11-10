from odoo.exceptions import ValidationError
from odoo.tests import tagged

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
