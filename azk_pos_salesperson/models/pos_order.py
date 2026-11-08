from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # Order salesperson: set by "Assign Salesperson to Order"; lines added
    # afterwards inherit it. Synced with the order so it survives reloads.
    salesperson_id = fields.Many2one('pos.sale.person', string='Order Salesperson', ondelete='restrict', index='btree_not_null')
