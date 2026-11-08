from odoo.tests import tagged

from .common import AzkTBCommon

TOTAL_KEYS = ('init_balance', 'debit', 'credit', 'period_balance', 'end_balance')


@tagged('post_install', '-at_install')
class TestDisplay(AzkTBCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        c1 = cls.company_data
        Account = cls.env['account.account']
        misc, payable = c1['default_journal_misc'], c1['default_account_payable']

        # 3-level tree: L1 > L2 > (leaf_a, leaf_b)
        cls.level_1 = Account.create({'code': '160000', 'name': 'L1 Assets', 'account_type': 'asset_current'})
        cls.level_2 = Account.create({'code': '161000', 'name': 'L2 Assets', 'account_type': 'asset_current', 'parent_id': cls.level_1.id})
        cls.leaf_a = Account.create({'code': '161100', 'name': 'Leaf A', 'account_type': 'asset_current', 'parent_id': cls.level_2.id})
        cls.leaf_b = Account.create({'code': '161200', 'name': 'Leaf B', 'account_type': 'asset_current', 'parent_id': cls.level_2.id})
        cls._azk_move(misc, '2016-04-01', [(cls.leaf_a, 300.0, 0.0), (cls.leaf_b, 0.0, 50.0), (payable, 0.0, 250.0)]).action_post()
        cls._azk_move(misc, '2017-04-01', [(cls.leaf_a, 20.0, 0.0), (payable, 0.0, 20.0)]).action_post()

        # Account whose movements cancel out inside the period (must stay with skip-zero)
        cls.cancelling = Account.create({'code': '170000', 'name': 'Cancelling', 'account_type': 'asset_current'})
        cls._azk_move(misc, '2017-05-01', [(cls.cancelling, 100.0, 0.0), (payable, 0.0, 100.0)]).action_post()
        cls._azk_move(misc, '2017-05-02', [(cls.cancelling, 0.0, 100.0), (payable, 100.0, 0.0)]).action_post()

        # All-zero account (initial nets to 0, no movement), alone under its parent
        cls.zero_parent = Account.create({'code': '180000', 'name': 'Zero Parent', 'account_type': 'asset_current'})
        cls.zero = Account.create({'code': '180100', 'name': 'All Zero', 'account_type': 'asset_current', 'parent_id': cls.zero_parent.id})
        cls._azk_move(misc, '2016-05-01', [(cls.zero, 100.0, 0.0), (payable, 0.0, 100.0)]).action_post()
        cls._azk_move(misc, '2016-05-02', [(cls.zero, 0.0, 100.0), (payable, 100.0, 0.0)]).action_post()

    def _values(self, hierarchy=True, **azk_tb):
        options = self._options(self.report, '2017-01-01', '2017-12-31', hierarchy=hierarchy, azk_tb=azk_tb)
        return self._tb_values(self.report, options)

    def test_skip_zero_keeps_cancelling_movements(self):
        shown = self._values(hierarchy=False)
        self.assertIn(self.zero.id, shown, 'all-zero account is listed without the option')

        skipped = self._values(hierarchy=False, skip_zero_balance=True)
        self.assertNotIn(self.zero.id, skipped)
        self.assertIn(self.cancelling.id, skipped)
        self.assertAlmostEqual(skipped[self.cancelling.id]['debit'], 100.0, places=2)
        self.assertAlmostEqual(skipped[self.cancelling.id]['credit'], 100.0, places=2)
        for key in TOTAL_KEYS:
            self.assertAlmostEqual(skipped['TOTAL'][key], shown['TOTAL'][key], places=2, msg=key)

    def test_skip_zero_drops_empty_parent(self):
        shown = self._values()
        self.assertIn(f'PARENT:{self.zero_parent.id}', shown)
        skipped = self._values(skip_zero_balance=True)
        self.assertNotIn(f'PARENT:{self.zero_parent.id}', skipped)
        self.assertNotIn(self.zero.id, skipped)

    def test_level_rollup_keeps_totals(self):
        full = self._values()
        expected_presence = {
            1: {f'PARENT:{self.level_1.id}'},
            2: {f'PARENT:{self.level_1.id}', f'PARENT:{self.level_2.id}'},
            3: {f'PARENT:{self.level_1.id}', f'PARENT:{self.level_2.id}', self.leaf_a.id, self.leaf_b.id},
        }
        hidden = {
            1: {f'PARENT:{self.level_2.id}', self.leaf_a.id, self.leaf_b.id},
            2: {self.leaf_a.id, self.leaf_b.id},
            3: set(),
        }
        for level in (1, 2, 3):
            values = self._values(account_level=level)
            self.assertLessEqual(expected_presence[level], set(values), f'level {level}')
            self.assertFalse(hidden[level] & set(values), f'level {level}')
            for key in TOTAL_KEYS:
                self.assertAlmostEqual(values['TOTAL'][key], full['TOTAL'][key], places=2, msg=f'level {level} {key}')
            # the level-1 parent still carries the whole subtree
            parent = values[f'PARENT:{self.level_1.id}']
            self.assertAlmostEqual(parent['init_balance'], 250.0, places=2)
            self.assertAlmostEqual(parent['end_balance'], 270.0, places=2)

    def test_level_ignored_without_hierarchy(self):
        flat = self._values(hierarchy=False)
        flat_with_level = self._values(hierarchy=False, account_level=1)
        self.assertEqual(set(flat), set(flat_with_level))
        self.assertIn(self.leaf_a.id, flat_with_level)

    # ------------------------------------------------------------------
    # Task 5: Show Amount Currency
    # ------------------------------------------------------------------
    def _post_cad_move(self):
        c1 = self.company_data
        cad = self.other_currency
        self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2017-06-01',
            'journal_id': c1['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'name': 'cad', 'account_id': self.leaf_a.id, 'currency_id': cad.id,
                        'amount_currency': 300.0, 'debit': 150.0, 'credit': 0.0}),
                (0, 0, {'name': 'cad', 'account_id': c1['default_account_payable'].id, 'currency_id': cad.id,
                        'amount_currency': -300.0, 'debit': 0.0, 'credit': 150.0}),
            ],
        }).action_post()
        return cad

    def _amount_currency_options(self, hierarchy, show):
        return self._options(self.report, '2017-01-01', '2017-12-31', hierarchy=hierarchy,
                             azk_tb={'show_amount_currency': show})

    def test_amount_currency_lines_sum_to_account(self):
        cad = self._post_cad_move()
        usd = self.company_data['company'].currency_id
        without = self._tb_values(self.report, self._amount_currency_options(False, False))
        options = self._amount_currency_options(False, True)
        lines = self.report._get_lines(options)
        values = self._tb_values(self.report, options, lines=lines)

        usd_key, cad_key = f'{self.leaf_a.id}:{usd.id}', f'{self.leaf_a.id}:{cad.id}'
        self.assertNotIn(self.leaf_a.id, values, 'account line is replaced by its currency lines')
        self.assertIn(usd_key, values)
        self.assertIn(cad_key, values)
        # Leaf A: 300 (2016) + 20 (2017, USD) + 150 (2017, CAD at company rate)
        self.assertAlmostEqual(without[self.leaf_a.id]['end_balance'], 470.0, places=2)
        self.assertAlmostEqual(values[usd_key]['end_balance'] + values[cad_key]['end_balance'], 470.0, places=2)
        self.assertAlmostEqual(values[cad_key]['end_balance'], 150.0, places=2)
        self.assertAlmostEqual(values[cad_key]['_sections']['end_balance']['amount_currency'], 300.0, places=2)
        cad_line = next(line for line in lines if self._line_key(self.report, line) == cad_key)
        self.assertTrue(cad_line.name.endswith(f'({cad.name})'), cad_line.name)
        for key in TOTAL_KEYS:
            self.assertAlmostEqual(values['TOTAL'][key], without['TOTAL'][key], places=2, msg=key)

    def test_amount_currency_parent_blank(self):
        self._post_cad_move()
        options = self._amount_currency_options(True, True)
        lines = self.report._get_lines(options)
        for line in lines:
            key = self._line_key(self.report, line)
            if key in (f'PARENT:{self.level_2.id}', f'PARENT:{self.level_1.id}', 'TOTAL'):
                cells = [c for c in line.columns if c.expression_label == 'amount_currency']
                self.assertTrue(cells, key)
                for cell in cells:
                    self.assertIsNone(cell.no_format, f'{key} must not sum mixed currencies')

    def test_amount_currency_column_hidden_when_off(self):
        options = self._amount_currency_options(False, False)
        self.assertFalse([c for c in options['columns'] if c['expression_label'] == 'amount_currency'])

        options = self._amount_currency_options(False, True)
        ac_columns = [c for c in options['columns'] if c['expression_label'] == 'amount_currency']
        self.assertEqual(len(ac_columns), 1)
        group = options['column_groups'][ac_columns[0]['column_group_index']]
        self.assertEqual(group['forced_options']['trial_balance_column_type'], 'end_balance')

    def test_amount_currency_shows_symbol(self):
        """Spec: the Amount Currency column shows the amount with the symbol of
        its currency (found missing during the manual Preview check)."""
        cad = self._post_cad_move()
        options = self._amount_currency_options(False, True)
        # Odoo only prints currency symbols when the user is in the
        # multi-currency group; the foreign amount needs its symbol regardless.
        options['multi_currency'] = False
        lines = self.report._get_lines(options)
        cad_line = next(line for line in lines if self._line_key(self.report, line) == f'{self.leaf_a.id}:{cad.id}')
        cell = next(c for c in cad_line.columns if c.expression_label == 'amount_currency')
        self.assertIn(cad.symbol, cell.name)
        self.assertIn('300', cell.name)
        self.assertEqual(cell.no_format, 300.0, 'raw value kept for exports')
