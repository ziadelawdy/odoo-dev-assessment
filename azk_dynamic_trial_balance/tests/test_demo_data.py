from odoo import fields
from odoo.tests import tagged

from .common import AzkTBCommon

PARITY_KEYS = ('init_balance', 'debit', 'credit', 'period_balance', 'end_balance')


@tagged('post_install', '-at_install')
class TestDemoData(AzkTBCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['azk.dynamic.trial.balance.report.handler']._azk_create_demo_data()
        cls.company = cls.env.company
        fiscal_year = cls.company.compute_fiscalyear_dates(fields.Date.context_today(cls.env['res.company']))
        cls.date_from = fields.Date.to_string(fiscal_year['date_from'])
        cls.date_to = fields.Date.to_string(fiscal_year['date_to'])

    def _demo_account(self, code):
        return self.env['account.account'].search([
            ('code', '=', code), *self.env['account.account']._check_company_domain(self.company),
        ], limit=1)

    def _company_only(self, report):
        return report.with_context(allowed_company_ids=self.company.ids)

    def test_demo_loader_is_idempotent(self):
        count = self.env['account.move'].search_count([('ref', '=like', 'AZK-DTB-DEMO%')])
        self.env['azk.dynamic.trial.balance.report.handler']._azk_create_demo_data()
        self.assertEqual(self.env['account.move'].search_count([('ref', '=like', 'AZK-DTB-DEMO%')]), count)

    def test_demo_content(self):
        bank = self._demo_account('1110')
        self.assertTrue(bank.parent_id, 'demo accounts form a hierarchy')
        self.assertTrue(bank.parent_id.parent_id, 'hierarchy is at least 3 levels deep')
        moves = self.env['account.move'].search([('ref', '=like', 'AZK-DTB-DEMO%')])
        self.assertEqual(set(moves.mapped('state')), {'posted', 'draft', 'cancel'})
        self.assertGreaterEqual(len(moves.line_ids.currency_id - self.company.currency_id), 2)
        self.assertTrue(moves.line_ids.filtered('analytic_distribution'))
        fiscal_starts = {self.company.compute_fiscalyear_dates(move.date)['date_from'] for move in moves}
        self.assertGreaterEqual(len(fiscal_starts), 2, 'demo spans two fiscal years')

    def test_demo_parity(self):
        ours, native = self._company_only(self.report), self._company_only(self.native)
        for hierarchy in (False, True):
            ours_values = self._tb_values(ours, self._options(ours, self.date_from, self.date_to, hierarchy=hierarchy))
            native_values = self._tb_values(native, self._options(native, self.date_from, self.date_to, hierarchy=hierarchy))
            accounts = {k for k in native_values if isinstance(k, int) or str(k).startswith(('UNDISTRIBUTED', 'PARENT'))}
            self.assertEqual(accounts, {k for k in ours_values if k in accounts or isinstance(k, int)})
            for key in accounts:
                for value_key in PARITY_KEYS:
                    self.assertAlmostEqual(ours_values[key][value_key], native_values[key][value_key], places=2,
                                           msg=f'hierarchy={hierarchy} {key} {value_key}')
            total = ours_values['TOTAL']['_sections']
            for section in ('initial_balance', 'end_balance'):
                self.assertAlmostEqual(total[section]['debit'], total[section]['credit'], places=2, msg=section)
