from odoo import fields, models
from odoo.tools import SQL


class PosOrderReport(models.Model):
    """Native POS analysis (one row per order line) + the line's salesperson and commission."""
    _inherit = 'report.pos.order'

    salesperson_id = fields.Many2one('pos.sale.person', string='Salesperson', readonly=True)
    azk_commission = fields.Monetary(string='Commission', readonly=True)

    def _select(self):
        # Commission = the native untaxed amount expression (sign of refunds,
        # currency rate) x the rate frozen on the line at sale time.
        return SQL("""%s,
            l.salesperson_id AS salesperson_id,
            ROUND(
                (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal))
                / COALESCE(NULLIF(s.currency_rate, 0), 1.0)
                * COALESCE(l.azk_commission_rate, 0) / 100,
                cu.decimal_places
            ) AS azk_commission
        """, super()._select())
