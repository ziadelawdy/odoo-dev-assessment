from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    active_salesperson_feature = fields.Boolean(
        string='Salesperson Assignment',
        help='Assign salespersons to order lines in this Point of Sale and print them on the receipt.',
    )
    allowed_sale_person_ids = fields.Many2many(
        'pos.sale.person', string='Allowed Salespersons',
        help='Salespersons available for assignment in this Point of Sale.',
    )
