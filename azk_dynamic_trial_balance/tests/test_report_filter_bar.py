"""In-report filter bar (user request after manual testing): the wizard options
can be changed directly in the report, like the native report filters."""
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingHttpCommon

from .common import AzkTBCommon


@tagged('post_install', '-at_install')
class TestFilterBarOptions(AzkTBCommon):

    def _opts(self, **extra):
        return self._options(self.report, '2017-01-01', '2017-12-31', **extra)

    def test_custom_filters_component(self):
        options = self._opts()
        components = options['custom_display_config'].get('components', {})
        self.assertEqual(components.get('AccountReportFilters'), 'AzkTrialBalanceFilters')

    def test_pdf_and_xlsx_buttons_in_bar(self):
        buttons = {button['action_param']: button for button in self._opts()['buttons'] if button.get('action') == 'export_file'}
        self.assertEqual(buttons['export_to_pdf']['name'], 'PDF')
        self.assertEqual(buttons['export_to_xlsx']['name'], 'XLSX')
        self.assertTrue(buttons['export_to_pdf']['always_show'])
        self.assertTrue(buttons['export_to_xlsx']['always_show'])

    def test_native_journal_filter(self):
        self.assertTrue(self.report.filter_journals)
        sale = self.company_data['default_journal_sale']
        options = self._opts(journals=[{'id': sale.id, 'selected': True}])
        self.assertEqual([j['id'] for j in options['journals'] if j.get('selected')], [sale.id])
        values = self._tb_values(self.report, options)
        receivable = self.company_data['default_account_receivable']
        self.assertAlmostEqual(values[receivable.id]['debit'], 1000.0, places=2)
        self.assertNotIn(self.company_data['default_account_payable'].id, values)

    def test_wizard_maps_journals_to_native_filter(self):
        sale = self.company_data['default_journal_sale']
        wizard = self.env['azk.dynamic.trial.balance.wizard'].create({
            'date_from': '2017-01-01', 'date_to': '2017-12-31', 'journal_ids': [(6, 0, sale.ids)],
        })
        options = wizard._build_report_options()
        self.assertEqual([j['id'] for j in options['journals'] if j.get('selected')], [sale.id])


@tagged('post_install', '-at_install')
class TestFilterBarTour(AccountTestInvoicingHttpCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']
        parent = Account.create({'code': '150000', 'name': 'Tour Parent', 'account_type': 'asset_current'})
        child = Account.create({'code': '150001', 'name': 'Tour Child', 'account_type': 'asset_current', 'parent_id': parent.id})
        move = cls.env['account.move'].create({
            'move_type': 'entry',
            'date': '2026-01-15',
            'journal_id': cls.company_data['default_journal_misc'].id,
            'line_ids': [
                (0, 0, {'name': 'tour', 'account_id': child.id, 'debit': 100.0, 'credit': 0.0}),
                (0, 0, {'name': 'tour', 'account_id': cls.company_data['default_account_payable'].id, 'debit': 0.0, 'credit': 100.0}),
            ],
        })
        move.action_post()

    def test_filter_bar_tour(self):
        self.start_tour(
            '/odoo/action-azk_dynamic_trial_balance.action_azk_dynamic_trial_balance_report',
            'azk_tb_filter_bar', login=self.env.user.login,
        )
