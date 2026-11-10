from odoo import fields, models, tools
from odoo.tools import SQL


class SalespersonPerformanceReport(models.Model):
    """One row per (POS order, salesperson): the salesperson's share of the order.

    The pivot cannot divide two sums, so the per-order amount is exposed twice:
    summed (sales) and averaged (average order value). Amounts use the same
    expressions as the native ``report.pos.order`` (refund sign, currency rate).
    """
    _name = 'azk.pos.salesperson.report'
    _description = 'POS Salesperson Performance'
    _auto = False
    _order = 'date desc'
    _rec_name = 'order_id'

    date = fields.Datetime(string='Order Date', readonly=True)
    order_id = fields.Many2one('pos.order', string='Order', readonly=True)
    salesperson_id = fields.Many2one('pos.sale.person', string='Salesperson', readonly=True)
    config_id = fields.Many2one('pos.config', string='Point of Sale', readonly=True)
    session_id = fields.Many2one('pos.session', string='Session', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    state = fields.Selection(
        [('draft', 'New'), ('cancel', 'Cancelled'), ('paid', 'Paid'), ('done', 'Posted')],
        string='Status', readonly=True)
    order_count = fields.Integer(string='Orders', readonly=True)
    line_count = fields.Integer(string='Lines', readonly=True)
    product_qty = fields.Float(string='Items', readonly=True)
    amount_untaxed = fields.Monetary(string='Sales w/o Tax', readonly=True)
    amount_total = fields.Monetary(string='Sales incl. Tax', readonly=True)
    average_order_value = fields.Monetary(string='Average Order Value', readonly=True, aggregator='avg')
    commission = fields.Monetary(string='Commission', readonly=True)

    def _query(self):
        untaxed = SQL("""ROUND(
                (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal))
                / COALESCE(NULLIF(s.currency_rate, 0), 1.0), cu.decimal_places)""")
        return SQL("""
            SELECT
                MIN(l.id) AS id,
                s.id AS order_id,
                l.salesperson_id AS salesperson_id,
                s.date_order AS date,
                ps.config_id AS config_id,
                s.session_id AS session_id,
                s.partner_id AS partner_id,
                s.company_id AS company_id,
                co.currency_id AS currency_id,
                s.state AS state,
                1 AS order_count,
                COUNT(l.id) AS line_count,
                SUM(l.qty) AS product_qty,
                SUM(%(untaxed)s) AS amount_untaxed,
                SUM(%(untaxed)s) AS average_order_value,
                SUM(ROUND(
                    (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal_incl))
                    / COALESCE(NULLIF(s.currency_rate, 0), 1.0), cu.decimal_places)) AS amount_total,
                SUM(ROUND(
                    (SIGN(l.qty) * SIGN(l.price_unit) * ABS(l.price_subtotal))
                    / COALESCE(NULLIF(s.currency_rate, 0), 1.0)
                    * COALESCE(l.azk_commission_rate, 0) / 100, cu.decimal_places)) AS commission
            FROM pos_order_line l
                JOIN pos_order s ON s.id = l.order_id
                LEFT JOIN pos_session ps ON ps.id = s.session_id
                LEFT JOIN res_company co ON co.id = s.company_id
                LEFT JOIN res_currency cu ON cu.id = co.currency_id
            GROUP BY s.id, l.salesperson_id, ps.config_id, co.currency_id, cu.decimal_places
        """, untaxed=untaxed)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL(
            "CREATE OR REPLACE VIEW %s AS (%s)", SQL.identifier(self._table), self._query()))
