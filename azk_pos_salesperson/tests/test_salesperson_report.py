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
