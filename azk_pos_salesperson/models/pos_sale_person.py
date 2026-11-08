from odoo import api, fields, models


class PosSalePerson(models.Model):
    """Salesperson credited for POS order lines (commission tracking).

    Loaded into the POS (offline) for the configs that allow them.
    """
    _name = 'pos.sale.person'
    _description = 'POS Salesperson'
    _inherit = ['pos.load.mixin']
    _order = 'name'

    name = fields.Char(required=True)
    phone_number = fields.Char(string='Phone Number')
    employee_id = fields.Many2one('hr.employee', string='Related Employee', ondelete='set null')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model
    def _load_pos_data_domain(self, data):
        config = data['pos.config']
        if not config.active_salesperson_feature:
            return [('id', '=', False)]
        return [('id', 'in', config.allowed_sale_person_ids.ids)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ['id', 'name', 'phone_number', 'employee_id']
