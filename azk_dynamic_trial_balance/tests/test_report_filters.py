from odoo.fields import Domain
from odoo.tests import tagged

from .common import AzkTBCommon

PARITY_KEYS = ('init_balance', 'debit', 'credit', 'period_balance', 'end_balance')
SUMMARY_WARNING = 'azk_dynamic_trial_balance.warning_filter_summary'
ANALYTIC_WARNING = 'azk_dynamic_trial_balance.warning_analytic_unbalanced'


@tagged('post_install', '-at_install')
class TestFilters(AzkTBCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        c1 = cls.company_data
        cls.unaffected = cls.env['account.account'].search([
            ('account_type', '=', 'equity_unaffected'),
            ('company_ids', 'in', c1['company'].ids),
        ], limit=1)

        plan = cls.env['account.analytic.plan'].create({'name': 'Departments'})
        cls.analytic_a = cls.env['account.analytic.account'].create({'name': 'Dept A', 'plan_id': plan.id})
        cls.analytic_b = cls.env['account.analytic.account'].create({'name': 'Dept B', 'plan_id': plan.id})
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2017-03-01',
            'journal_id': c1['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {
                    'name': 'split expense', 'account_id': c1['default_account_expense'].id,
                    'debit': 1000.0, 'credit': 0.0,
                    'analytic_distribution': {str(cls.analytic_a.id): 60, str(cls.analytic_b.id): 40},
                }),
                (0, 0, {'name': 'split expense', 'account_id': c1['default_account_payable'].id, 'debit': 0.0, 'credit': 1000.0}),
            ],
        })
        move.action_post()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _ours(self, **azk_tb):
        options = self._options(self.report, '2017-01-01', '2017-12-31', azk_tb=azk_tb)
        return options, self._tb_values(self.report, options)

    def _native(self, forced_domain=None):
        options = self._options(self.native, '2017-01-01', '2017-12-31')
        if forced_domain is not None:
            options['forced_domain'] = list(options.get('forced_domain', [])) + list(forced_domain)
        return self._tb_values(self.native, options)

    @staticmethod
    def _account_keys(values):
        return {k for k in values if isinstance(k, int)}

    def _assert_account_parity(self, ours, native, msg=''):
        self.assertEqual(self._account_keys(ours), self._account_keys(native), msg)
        for key in self._account_keys(native):
            for value_key in PARITY_KEYS:
                self.assertAlmostEqual(ours[key][value_key], native[key][value_key], places=2, msg=f'{key} {value_key} {msg}')

    def _warnings(self, options):
        warnings = {}
        self.report._get_lines(options, warnings=warnings)
        return warnings

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------
    def test_journal_filter_parity(self):
        sale = self.company_data['default_journal_sale']
        _options, ours = self._ours(journal_ids=[sale.id])
        native = self._native([('journal_id', 'in', [sale.id])])
        self.assertTrue(self._account_keys(ours))
        self._assert_account_parity(ours, native)
        receivable = self.company_data['default_account_receivable']
        self.assertAlmostEqual(ours[receivable.id]['debit'], 1000.0, places=2)
        payable = self.company_data['default_account_payable']
        self.assertNotIn(payable.id, ours, 'payable has no entry in the sale journal')

    def test_multiple_prefixes(self):
        _options, ours = self._ours(account_prefixes=['1', '40'])
        accounts = self.env['account.account'].browse(list(self._account_keys(ours)))
        self.assertTrue(accounts)
        for account in accounts:
            self.assertTrue(account.code.startswith(('1', '40')), account.code)
        prefix_domain = Domain.OR([[('account_id.code', '=like', '1%')], [('account_id.code', '=like', '40%')]])
        self._assert_account_parity(ours, self._native(list(prefix_domain)))

    def test_prefix_and_undistributed_line(self):
        company_id = self.company_data['company'].id
        undistributed = f'UNDISTRIBUTED:{company_id}'

        _options, ours = self._ours(account_prefixes=['1'])
        self.assertFalse([k for k in ours if str(k).startswith('UNDISTRIBUTED')])
        accounts = [v for k, v in ours.items() if isinstance(k, int)]
        self.assertAlmostEqual(ours['TOTAL']['init_balance'], sum(v['init_balance'] for v in accounts), places=2)
        self.assertAlmostEqual(ours['TOTAL']['debit'], sum(v['debit'] for v in accounts), places=2)
        self.assertAlmostEqual(ours['TOTAL']['credit'], sum(v['credit'] for v in accounts), places=2)

        _options, ours = self._ours(account_prefixes=[self.unaffected.code[:3]])
        native = self._native()
        self.assertIn(undistributed, ours)
        self.assertAlmostEqual(ours[undistributed]['init_balance'], native[undistributed]['init_balance'], places=2)
        self.assertNotAlmostEqual(native[undistributed]['init_balance'], 0.0, places=2)

    def test_analytic_proportional_share(self):
        expense = self.company_data['default_account_expense']
        _options, ours_a = self._ours(analytic_account_ids=[self.analytic_a.id])
        _options, ours_b = self._ours(analytic_account_ids=[self.analytic_b.id])
        self.assertAlmostEqual(ours_a[expense.id]['debit'], 600.0, places=2)
        self.assertAlmostEqual(ours_b[expense.id]['debit'], 400.0, places=2)
        payable = self.company_data['default_account_payable']
        self.assertNotIn(payable.id, ours_a, 'accounts without analytic distribution are not reported')

    def test_analytic_unbalanced_notice(self):
        options, _values = self._ours(analytic_account_ids=[self.analytic_a.id])
        warnings = self._warnings(options)
        self.assertIn(ANALYTIC_WARNING, warnings)
        self.assertEqual(warnings[ANALYTIC_WARNING].get('alert_type'), 'warning')
        self.assertIn(SUMMARY_WARNING, warnings)
        self.assertIn('Dept A', warnings[SUMMARY_WARNING]['summary'])

        options, _values = self._ours()
        warnings = self._warnings(options)
        self.assertNotIn(ANALYTIC_WARNING, warnings)
        self.assertNotIn(SUMMARY_WARNING, warnings)

    def test_prefix_sanitized(self):
        options, ours = self._ours(account_prefixes=["1%' OR 1=1", '  ', '1_'])
        self.assertEqual(options['azk_tb']['account_prefixes'], [])
        self._assert_account_parity(ours, self._native())
