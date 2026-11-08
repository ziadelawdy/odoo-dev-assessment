from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import AzkTBCommon


@tagged('post_install', '-at_install')
class TestWizard(AzkTBCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = cls.env['account.analytic.plan'].create({'name': 'Wizard Plan'})
        other_plan = cls.env['account.analytic.plan'].create({'name': 'Other Plan'})
        cls.analytic_1 = cls.env['account.analytic.account'].create({'name': 'W1', 'plan_id': plan.id})
        cls.analytic_2 = cls.env['account.analytic.account'].create({'name': 'W2', 'plan_id': other_plan.id})
        # The native hierarchy option is only available when parent accounts exist.
        parent = cls.env['account.account'].create({'code': '190000', 'name': 'Wizard Parent', 'account_type': 'asset_current'})
        cls.env['account.account'].create({
            'code': '190100', 'name': 'Wizard Child', 'account_type': 'asset_current', 'parent_id': parent.id,
        })

    def _wizard(self, **values):
        return self.env['azk.dynamic.trial.balance.wizard'].create({
            'date_from': '2017-01-01',
            'date_to': '2017-12-31',
            **values,
        })

    def test_build_options_maps_fields(self):
        sale = self.company_data['default_journal_sale']
        wizard = self._wizard(
            include_unposted=True,
            hierarchy_subtotals=True,
            hierarchy_only_parents=True,
            account_level='2',
            account_prefixes='1, 40',
            journal_ids=[(6, 0, sale.ids)],
            analytic_account_ids=[(6, 0, self.analytic_1.ids)],
            skip_zero_balance=True,
            show_amount_currency=True,
        )
        options = wizard._build_report_options()
        self.assertEqual(options['report_id'], self.report.id)
        self.assertEqual(options['date']['date_from'], '2017-01-01')
        self.assertEqual(options['date']['date_to'], '2017-12-31')
        self.assertTrue(options['all_entries'])
        self.assertTrue(options['hierarchy'])
        self.assertEqual(options['azk_tb'], {
            'journal_ids': sale.ids,
            'account_prefixes': ['1', '40'],
            'analytic_account_ids': self.analytic_1.ids,
            'skip_zero_balance': True,
            'account_level': 2,
            'show_amount_currency': True,
        })

    def test_level_only_with_parents_only_option(self):
        wizard = self._wizard(hierarchy_subtotals=True, hierarchy_only_parents=False, account_level='2')
        self.assertFalse(wizard._build_report_options()['azk_tb']['account_level'])

    def test_options_survive_rerender(self):
        wizard = self._wizard(account_prefixes='1', skip_zero_balance=True)
        options = wizard._build_report_options()
        rerendered = self.report.get_options(previous_options=options)
        self.assertEqual(rerendered['azk_tb'], options['azk_tb'])
        self.assertEqual(rerendered['forced_domain'], options['forced_domain'])

    def test_preview_action(self):
        action = self._wizard(account_prefixes='1').action_preview()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'account_report')
        self.assertEqual(action['context']['report_id'], self.report.id)
        self.assertTrue(action['params']['ignore_session'])
        self.assertEqual(action['params']['options']['azk_tb']['account_prefixes'], ['1'])

    def test_dates_validation(self):
        with self.assertRaises(ValidationError):
            self._wizard(date_from='2017-12-31', date_to='2017-01-01')

    def test_analytic_single_plan(self):
        with self.assertRaises(ValidationError):
            self._wizard(analytic_account_ids=[(6, 0, (self.analytic_1 + self.analytic_2).ids)])

    def test_access_rights(self):
        user = new_test_user(self.env, login='azk_tb_plain_user', groups='base.group_user')
        with self.assertRaises(AccessError):
            self.env['azk.dynamic.trial.balance.wizard'].with_user(user).create({
                'date_from': '2017-01-01', 'date_to': '2017-12-31',
            })
