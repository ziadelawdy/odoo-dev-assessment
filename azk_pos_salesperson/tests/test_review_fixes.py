"""Regression tests for the findings of the independent whole-branch review."""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.point_of_sale.tests.common_setup_methods import setup_product_combo_items
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon

from .common import AzkPosSalespersonCommon


@tagged('post_install', '-at_install')
class TestSalespersonReviewBackend(AzkPosSalespersonCommon):

    def test_employee_not_loaded_in_pos(self):
        # loading employee_id would pull hr.employee records (pos_hr cashiers) into the POS store
        self.assertNotIn('employee_id', self.env['pos.sale.person']._load_pos_data_fields(self.config))

    def test_allowed_salespersons_same_company(self):
        other_company = self.env['res.company'].create({'name': 'Other Company'})
        foreign = self.env['pos.sale.person'].create({'name': 'Foreign', 'company_id': other_company.id})
        with self.assertRaises((UserError, ValidationError)):
            self.config.write({'allowed_sale_person_ids': [(4, foreign.id)]})

    def test_salesperson_company_rule(self):
        other_company = self.env['res.company'].create({'name': 'Other Company'})
        foreign = self.env['pos.sale.person'].create({'name': 'Foreign', 'company_id': other_company.id})
        user = new_test_user(
            self.env, login='azk_mc_user', groups='point_of_sale.group_pos_user',
            company_id=self.env.company.id, company_ids=[(6, 0, self.env.company.ids)],
        )
        with self.assertRaises(AccessError):
            foreign.with_user(user).read(['name'])
        shared = self.env['pos.sale.person'].create({'name': 'Shared', 'company_id': False})
        self.assertEqual(shared.with_user(user).name, 'Shared')


@tagged('post_install', '-at_install')
class TestSalespersonReviewUi(TestPointOfSaleHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        SalePerson = cls.env['pos.sale.person']
        cls.sp_a = SalePerson.create({'name': 'Salesperson A'})
        cls.sp_c = SalePerson.create({'name': 'Salesperson C'})
        cls.main_pos_config.write({
            'active_salesperson_feature': True,
            'allowed_sale_person_ids': [(6, 0, (cls.sp_a | cls.sp_c).ids)],
        })

    def _orders(self):
        return self.env['pos.order'].search([('config_id', '=', self.main_pos_config.id)], order='id')

    def test_combo_edit_keeps_salesperson(self):
        setup_product_combo_items(self)
        self.start_pos_tour('AzkSalespersonComboEditTour')
        order = self._orders()[-1]
        self.assertEqual(len(order.lines), 4)
        self.assertEqual(set(order.lines.salesperson_id.ids), {self.sp_c.id})

    def test_pos_refund_keeps_salesperson(self):
        self.start_pos_tour('AzkSalespersonRefundTour')
        sale, refund = self._orders()[-2:]
        self.assertEqual(sale.lines.salesperson_id, self.sp_a)
        self.assertLess(refund.lines.qty, 0)
        self.assertEqual(refund.lines.salesperson_id, self.sp_a)

    def test_refund_order_does_not_prompt(self):
        """Second review: the first-product question must not re-credit refund lines."""
        self.start_pos_tour('AzkSalespersonRefundNoPromptTour')
        _sale, refund = self._orders()[-2:]
        self.assertLess(refund.lines.qty, 0)
        self.assertEqual(refund.lines.salesperson_id, self.sp_a)

    def test_code_added_line_does_not_prompt(self):
        """Second review: lines added by code (configure=False) never open the question."""
        self.start_pos_tour('AzkSalespersonCodeLineNoPromptTour')
        order = self._orders()[-1]
        self.assertEqual(len(order.lines), 2)
        self.assertEqual(order.lines.salesperson_id, self.sp_a)


@tagged('post_install', '-at_install')
class TestSalespersonSmallScreen(TestPointOfSaleHttpCommon):
    browser_size = '375x667'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sp_a = cls.env['pos.sale.person'].create({'name': 'Salesperson A'})
        cls.main_pos_config.write({
            'active_salesperson_feature': True,
            'allowed_sale_person_ids': [(6, 0, cls.sp_a.ids)],
        })

    def test_order_button_on_small_screen(self):
        self.start_pos_tour('AzkSalespersonSmallScreenTour')
