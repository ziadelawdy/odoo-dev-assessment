from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    salesperson_id = fields.Many2one('pos.sale.person', string='Salesperson', ondelete='restrict', index='btree_not_null')

    @api.model
    def _load_pos_data_fields(self, config):
        return super()._load_pos_data_fields(config) + ['salesperson_id']
