from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    salesperson_id = fields.Many2one('pos.sale.person', string='Salesperson', ondelete='restrict', index='btree_not_null')
    # Commission rate frozen when the line is sold. Not a compute: the POS
    # re-sends whole lines (same salesperson) when an order is synced again,
    # and any write of salesperson_id would trigger a recompute with today's rate.
    azk_commission_rate = fields.Float(string='Commission Rate (%)', digits=(5, 2), readonly=True)

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['salesperson_id']

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'azk_commission_rate' not in vals:
                vals['azk_commission_rate'] = self._azk_rate_for(vals)
        return super().create(vals_list)

    @api.model
    def _azk_rate_for(self, vals):
        person = self.env['pos.sale.person'].browse(vals.get('salesperson_id') or [])
        if not person:
            return 0.0
        # a refund line keeps the rate of the sale it refunds
        refunded = self.browse(vals.get('refunded_orderline_id') or [])
        if refunded and refunded.salesperson_id == person:
            return refunded.azk_commission_rate
        return person.commission_rate

    def write(self, vals):
        if 'salesperson_id' not in vals or 'azk_commission_rate' in vals:
            return super().write(vals)
        person = self.env['pos.sale.person'].browse(vals['salesperson_id'] or [])
        changed = self.filtered(lambda line: line.salesperson_id != person)
        result = super().write(vals)
        if changed:
            changed.write({'azk_commission_rate': person.commission_rate})
        return result
