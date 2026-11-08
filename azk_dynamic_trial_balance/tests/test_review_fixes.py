"""Regression tests for the findings of the independent whole-branch review."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import AzkTBCommon

SECTIONS = ('initial_balance', 'period', 'end_balance')


@tagged('post_install', '-at_install')
class TestReviewFixes(AzkTBCommon):

    def _total_columns(self, report, options):
        """{(section, label): value} of the grand total line, read from raw lines."""
        lines = report._get_lines(options)
        total = lines[-1]
        self.assertEqual(report._get_markup(total.id), 'total')
        values = {}
        for column in total.columns:
            if column.column_group_index is None:
                continue
            section = options['column_groups'][column.column_group_index]['forced_options']['trial_balance_column_type']
            values[(section, column.expression_label)] = column.no_format or 0.0
        return lines, values

    def _assert_same_total(self, left, right, msg):
        for key in left:
            if key[1] == 'amount_currency':
                continue
            self.assertAlmostEqual(left[key], right[key], places=2, msg=f'{msg} {key}')

    def setUp(self):
        super().setUp()
        # What a user gets by adding groupings in the report UI (as in the
        # native test_trial_balance_unfold_all): accounts become unfoldable.
        self.report.line_ids[0].user_groupby = 'account_id, partner_id, id'

    def test_unfold_all_keeps_total(self):
        """Partner / journal-item sub-lines (unfolded accounts) are not account balances."""
        # One company only: with two currencies the native report drops its CTA
        # line under unfold_all (native behaviour, verified), which would make
        # folded/unfolded totals differ for reasons unrelated to this module.
        report = self.report.with_context(allowed_company_ids=self.company_data['company'].ids)
        for show_amount_currency in (False, True):
            base = dict(azk_tb={'show_amount_currency': show_amount_currency})
            _lines, folded = self._total_columns(report, self._options(report, '2017-01-01', '2017-12-31', **base))
            lines, unfolded = self._total_columns(
                report, self._options(report, '2017-01-01', '2017-12-31', unfold_all=True, **base))
            self.assertTrue(
                any(line.parent_id and self.report._get_markup(line.id) not in ('total', 'parent_account')
                    and self.report._parse_line_id(line.id)[-1][1] != 'account.account' for line in lines[:-1]),
                'unfold_all must expand sub-lines for this test to be meaningful',
            )
            self._assert_same_total(folded, unfolded, f'show_amount_currency={show_amount_currency}')
            ids = [line.id for line in lines]
            self.assertEqual(len(ids), len(set(ids)), 'line ids must stay unique')

    def test_expansion_has_no_earnings_lines(self):
        """Expanding one account must not append Undistributed P/L lines."""
        unaffected = self.env['account.account'].search([
            ('account_type', '=', 'equity_unaffected'),
            ('company_ids', 'in', self.company_data['company'].ids),
        ], limit=1)
        options = self._options(self.report, '2017-01-01', '2017-12-31',
                                azk_tb={'account_prefixes': [unaffected.code[:3], '1']})
        receivable = self.company_data['default_account_receivable']
        line = next(
            line for line in self.report._get_lines(options)
            if self.report._get_res_id_from_line_id(line.id, 'account.account') == receivable.id
        )
        expanded = self.report.get_expanded_lines(
            options, line.id, line.groupby, line.expand_function, None, None,
        )
        markups = [self.report._get_markup(sub.id if hasattr(sub, 'id') else sub['id']) for sub in expanded]
        self.assertTrue(expanded)
        self.assertNotIn('undistributed_profits_losses', markups)
        self.assertNotIn('cumulative_translation_adjustment', markups)

    def test_prefix_with_dash(self):
        """Odoo 20 account codes may contain '-' (ACCOUNT_CODE_REGEX)."""
        account = self.env['account.account'].create({'code': '1-500', 'name': 'Dashed', 'account_type': 'asset_current'})
        self._azk_move(self.company_data['default_journal_misc'], '2017-02-01', [
            (account, 25.0, 0.0), (self.company_data['default_account_payable'], 0.0, 25.0),
        ]).action_post()
        options = self._options(self.report, '2017-01-01', '2017-12-31', azk_tb={'account_prefixes': ['1-5']})
        self.assertEqual(options['azk_tb']['account_prefixes'], ['1-5'])
        values = self._tb_values(self.report, options)
        self.assertEqual({k for k in values if isinstance(k, int)}, {account.id})

    def test_wizard_rejects_invalid_prefix(self):
        """An invalid prefix must not silently produce an unfiltered report."""
        with self.assertRaises(ValidationError):
            self.env['azk.dynamic.trial.balance.wizard'].create({
                'date_from': '2017-01-01', 'date_to': '2017-12-31', 'account_prefixes': "1%' OR 1=1",
            })

    def test_comparison_periods_not_offered(self):
        """Comparison periods are out of scope (spec non-goal); the filter must not be offered."""
        self.assertFalse(self.report.filter_period_comparison)
        options = self._options(self.report, '2017-01-01', '2017-12-31')
        self.assertFalse(options.get('comparison', {}).get('number_period'))
