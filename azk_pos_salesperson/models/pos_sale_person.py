from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosSalePerson(models.Model):
    """Salesperson credited for POS order lines (commission tracking).

    Loaded into the POS (offline) for the configs that allow them.
    """
    _name = 'pos.sale.person'
    _description = 'POS Salesperson'
    _inherit = ['pos.load.mixin']
    _order = 'name'
    _check_company_auto = True

    name = fields.Char(required=True)
    phone_number = fields.Char(string='Phone Number')
    employee_id = fields.Many2one('hr.employee', string='Related Employee', ondelete='set null', check_company=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    commission_rate = fields.Float(
        string='Commission (%)', digits=(5, 2),
        help='Percentage of the sales without tax. It is copied onto each order line when the sale is made, '
             'so changing it later does not change past commissions.')

    @api.constrains('commission_rate')
    def _check_commission_rate(self):
        for person in self:
            if not 0 <= person.commission_rate <= 100:
                raise ValidationError(_('The commission of %s must be between 0 and 100%%.', person.name))

    @api.model
    def _load_pos_data_domain(self, data):
        config = data['pos.config']
        if not config.active_salesperson_feature:
            return [('id', '=', False)]
        return [
            ('id', 'in', config.allowed_sale_person_ids.ids),
            ('company_id', 'in', [False, config.company_id.id]),
        ]

    @api.model
    def _load_pos_data_fields(self, config):
        # employee_id stays backend-only: loading it would pull hr.employee
        # records (pos_hr cashiers) into the POS store.
        return ['id', 'name', 'phone_number']
