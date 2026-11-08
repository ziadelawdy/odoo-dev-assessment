from odoo.tests import tagged

from .common import AzkTBCommon


@tagged('post_install', '-at_install')
class TestEngine(AzkTBCommon):

    def test_parity_with_native_unfiltered(self):
        ours = self._tb_values(self.report, self._options(self.report, '2017-01-01', '2017-12-31'))
        native = self._tb_values(self.native, self._options(self.native, '2017-01-01', '2017-12-31'))
        self.assertTrue(native, 'native report returned no lines')
        self.assertParity(ours, native)

    # ------------------------------------------------------------------
    # Task 2: classic Debit/Credit split
    # ------------------------------------------------------------------
    def _period(self, report, date_from='2017-01-01', date_to='2017-12-31', **extra):
        options = self._options(report, date_from, date_to, **extra)
        return self._tb_values(report, options)

    def test_initial_end_classic_split(self):
        for key, vals in self._period(self.report).items():
            if key == 'TOTAL':
                continue
            for section in ('initial_balance', 'end_balance'):
                cols = vals['_sections'][section]
                self.assertGreaterEqual(cols['debit'], 0.0, f'{key} {section}')
                self.assertGreaterEqual(cols['credit'], 0.0, f'{key} {section}')
                self.assertAlmostEqual(cols['debit'] * cols['credit'], 0.0, places=2, msg=f'{key} {section}')
                self.assertAlmostEqual(cols['balance'], cols['debit'] - cols['credit'], places=2, msg=f'{key} {section}')

    def test_reversed_sign_account(self):
        """A payable (normally credit) carrying a debit balance shows it in the Debit column."""
        payable = self.company_data['default_account_payable']
        initial = self._period(self.report)[payable.id]['_sections']['initial_balance']
        self.assertAlmostEqual(initial['debit'], 100.0, places=2)
        self.assertAlmostEqual(initial['credit'], 0.0, places=2)

    def test_opening_only_account(self):
        payable = self.company_data['default_account_payable']
        vals = self._period(self.report)[payable.id]
        self.assertAlmostEqual(vals['init_balance'], 100.0, places=2)
        self.assertAlmostEqual(vals['end_balance'], 100.0, places=2)
        self.assertAlmostEqual(vals['debit'], 0.0, places=2)
        self.assertAlmostEqual(vals['credit'], 0.0, places=2)

    def test_pl_account_across_fiscal_year(self):
        c1 = self.company_data
        self._azk_move(c1['default_journal_misc'], '2016-12-31', [
            (c1['default_account_expense'], 50.0, 0.0),
            (c1['default_account_payable'], 0.0, 50.0),
        ]).action_post()
        ours = self._period(self.report)
        native = self._period(self.native)
        expense = c1['default_account_expense']
        self.assertAlmostEqual(ours[expense.id]['init_balance'], 0.0, places=2)
        undistributed = f"UNDISTRIBUTED:{c1['company'].id}"
        self.assertAlmostEqual(ours[undistributed]['init_balance'], native[undistributed]['init_balance'], places=2)
        # 2016 result was -100 (revenue 300 - expense 200); the extra 50 expense brings it to -50
        self.assertAlmostEqual(ours[undistributed]['init_balance'], -50.0, places=2)

    def test_last_day_and_day_before(self):
        c1 = self.company_data
        assets = c1['default_account_assets']
        self._azk_move(c1['default_journal_misc'], '2016-12-31', [
            (assets, 10.0, 0.0), (c1['default_account_payable'], 0.0, 10.0),
        ]).action_post()
        self._azk_move(c1['default_journal_misc'], '2017-12-31', [
            (assets, 7.0, 0.0), (c1['default_account_payable'], 0.0, 7.0),
        ]).action_post()
        vals = self._period(self.report)[assets.id]
        self.assertAlmostEqual(vals['init_balance'], 10.0, places=2)
        self.assertAlmostEqual(vals['debit'], 7.0, places=2)
        self.assertAlmostEqual(vals['end_balance'], 17.0, places=2)

    def test_hierarchy_parent_net_and_total_gross(self):
        c1 = self.company_data
        Account = self.env['account.account']
        parent = Account.create({'code': '150000', 'name': 'Parent Assets', 'account_type': 'asset_current'})
        child_a = Account.create({'code': '150001', 'name': 'Child A', 'account_type': 'asset_current', 'parent_id': parent.id})
        child_b = Account.create({'code': '150002', 'name': 'Child B', 'account_type': 'asset_current', 'parent_id': parent.id})
        self._azk_move(c1['default_journal_misc'], '2016-03-01', [
            (child_a, 100.0, 0.0), (child_b, 0.0, 30.0), (c1['default_account_payable'], 0.0, 70.0),
        ]).action_post()

        vals = self._period(self.report, hierarchy=True)
        parent_initial = vals[f'PARENT:{parent.id}']['_sections']['initial_balance']
        self.assertAlmostEqual(parent_initial['debit'], 70.0, places=2)
        self.assertAlmostEqual(parent_initial['credit'], 0.0, places=2)

        account_level = {k: v for k, v in vals.items() if k != 'TOTAL' and not str(k).startswith('PARENT:')}
        total = vals['TOTAL']['_sections']
        for section in ('initial_balance', 'end_balance'):
            expected_debit = sum(v['_sections'][section]['debit'] for v in account_level.values())
            expected_credit = sum(v['_sections'][section]['credit'] for v in account_level.values())
            self.assertAlmostEqual(total[section]['debit'], expected_debit, places=2, msg=section)
            self.assertAlmostEqual(total[section]['credit'], expected_credit, places=2, msg=section)
            self.assertAlmostEqual(total[section]['debit'], total[section]['credit'], places=2, msg=section)
            self.assertGreater(total[section]['debit'], 0.0, section)

    def test_multi_company_isolation(self):
        c1, c2 = self.company_data['company'], self.company_data_2['company']
        only_c1 = self.report.with_context(allowed_company_ids=[c1.id])
        vals = self._tb_values(only_c1, self._options(only_c1, '2017-01-01', '2017-12-31'))
        c2_accounts = {
            self.company_data_2[k].id
            for k in ('default_account_payable', 'default_account_revenue', 'default_account_expense')
        }
        self.assertFalse(c2_accounts & set(vals), 'company_2 accounts leaked')
        self.assertNotIn(f'UNDISTRIBUTED:{c2.id}', vals)

        both = [c1.id, c2.id]
        ours = self.report.with_context(allowed_company_ids=both)
        native = self.native.with_context(allowed_company_ids=both)
        self.assertParity(
            self._tb_values(ours, self._options(ours, '2017-01-01', '2017-12-31')),
            self._tb_values(native, self._options(native, '2017-01-01', '2017-12-31')),
        )

    def test_draft_and_cancelled(self):
        c1 = self.company_data
        receivable = c1['default_account_receivable']
        self._azk_move(c1['default_journal_misc'], '2017-05-01', [
            (receivable, 500.0, 0.0), (c1['default_account_revenue'], 0.0, 500.0),
        ])  # stays draft
        cancelled = self._azk_move(c1['default_journal_misc'], '2017-05-02', [
            (receivable, 9000.0, 0.0), (c1['default_account_revenue'], 0.0, 9000.0),
        ])
        cancelled.button_cancel()
        self.assertEqual(cancelled.state, 'cancel')

        for all_entries, expected in ((False, 1000.0), (True, 1500.0)):
            ours = self._period(self.report, all_entries=all_entries)
            native = self._period(self.native, all_entries=all_entries)
            self.assertAlmostEqual(ours[receivable.id]['debit'], expected, places=2, msg=f'all_entries={all_entries}')
            self.assertParity(ours, native, msg=f'all_entries={all_entries}')

    def test_default_options_multi_company_and_totals_below_sections(self):
        """Regression (found in the Preview): with several companies selected,
        Odoo defaults to 'consolidation' (lines grouped by account code), and
        'totals below sections' adds a total under every section. The grand
        total must still only sum real account balances."""
        c1, c2 = self.company_data['company'], self.company_data_2['company']
        c1.totals_below_sections = True
        Account = self.env['account.account']
        parent = Account.create({'code': '150000', 'name': 'Parent Assets', 'account_type': 'asset_current'})
        child = Account.create({'code': '150001', 'name': 'Child', 'account_type': 'asset_current', 'parent_id': parent.id})
        self._azk_move(self.company_data['default_journal_misc'], '2016-03-01', [
            (child, 100.0, 0.0), (self.company_data['default_account_payable'], 0.0, 100.0),
        ]).action_post()

        report = self.report.with_context(allowed_company_ids=[c1.id, c2.id])
        # Same previous_options as the wizard sends: no explicit 'consolidation' key
        options = report.get_options({
            'selected_variant_id': report.id,
            'date': {'date_from': '2017-01-01', 'date_to': '2017-12-31'},
            'hierarchy': True,
        })
        self.assertFalse(options['consolidation'], 'consolidation (group by code) is not offered')
        values = self._tb_values(report, options)
        self.assertIn(child.id, values)
        total = values['TOTAL']['_sections']
        for section in ('initial_balance', 'end_balance'):
            self.assertAlmostEqual(total[section]['debit'], total[section]['credit'], places=2, msg=section)
