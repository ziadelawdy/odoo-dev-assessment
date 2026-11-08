from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_active_salesperson_feature = fields.Boolean(related='pos_config_id.active_salesperson_feature', readonly=False)
    pos_allowed_sale_person_ids = fields.Many2many(related='pos_config_id.allowed_sale_person_ids', readonly=False)
