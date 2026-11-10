from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    salesperson_id = fields.Many2one('pos.sale.person', string='Salesperson', ondelete='restrict', index='btree_not_null')
    # Rate frozen at sale time: depends on the line's salesperson only, so a
    # later change of the salesperson's rate does not rewrite past commissions.
    azk_commission_rate = fields.Float(
        string='Commission Rate (%)', digits=(5, 2),
        compute='_compute_azk_commission_rate', store=True)

    @api.depends('salesperson_id')
    def _compute_azk_commission_rate(self):
        for line in self:
            line.azk_commission_rate = line.salesperson_id.commission_rate

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['salesperson_id']
