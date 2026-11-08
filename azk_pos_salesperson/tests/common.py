from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class AzkPosSalespersonCommon(TestPoSCommon):
    """Basic POS config with three salespersons; A and B are allowed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        SalePerson = cls.env['pos.sale.person']
        cls.sp_a = SalePerson.create({'name': 'Salesperson A', 'phone_number': '0100'})
        cls.sp_b = SalePerson.create({'name': 'Salesperson B'})
        cls.sp_c = SalePerson.create({'name': 'Salesperson C'})
        cls.config.write({
            'active_salesperson_feature': True,
            'allowed_sale_person_ids': [(6, 0, (cls.sp_a | cls.sp_b).ids)],
        })
        cls.product_x = cls.create_product('Product X', cls.categ_basic, 10.0)
        cls.product_y = cls.create_product('Product Y', cls.categ_basic, 20.0)

    def _sync_order(self, lines, order_vals=None):
        """lines: list of (product, qty, salesperson_or_False). Returns the pos.order."""
        line_args = []
        for product, qty, person in lines:
            args = {'product': product, 'quantity': qty}
            if person:
                args['salesperson_id'] = person.id
            line_args.append(args)
        data = self.create_ui_order_data(line_args, pos_order_ui_args=order_vals or {})
        result = self.env['pos.order'].sync_from_ui([data])
        return self.env['pos.order'].browse(result['pos.order'][0]['id'])
