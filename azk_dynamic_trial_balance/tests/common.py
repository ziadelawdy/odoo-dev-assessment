from odoo import fields
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon

VALUE_KEYS = ('init_balance', 'debit', 'credit', 'period_balance', 'end_balance')


class AzkTBCommon(TestAccountReportsCommon):
    """Shared fixture: the native Trial Balance test entries (2016/2017, two companies)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        context = {'allowed_company_ids': [cls.company_data['company'].id, cls.company_data_2['company'].id]}
        cls.company_data_2['default_account_payable'].with_context(context).code = '211010'
        cls.company_data_2['default_account_revenue'].with_context(context).code = '400010'
        cls.company_data_2['default_account_expense'].with_context(context).code = '600010'

        c1, c2 = cls.company_data, cls.company_data_2
        cls.move_2016_1 = cls._azk_move(c1['default_journal_misc'], '2016-01-01', [
            (c1['default_account_payable'], 100.0, 0.0),
            (c1['default_account_expense'], 200.0, 0.0),
            (c1['default_account_revenue'], 0.0, 300.0),
        ])
        cls.move_2016_2 = cls._azk_move(c2['default_journal_misc'], '2016-06-01', [
            (c2['default_account_payable'], 100.0, 0.0),
            (c2['default_account_revenue'], 0.0, 100.0),
        ])
        cls.move_2017_1 = cls._azk_move(c1['default_journal_sale'], '2017-01-01', [
            (c1['default_account_receivable'], 1000.0, 0.0),
            (c1['default_account_revenue'], 20000.0, 0.0),
            (c1['default_account_expense'], 0.0, 21000.0),
        ])
        cls.move_2017_2 = cls._azk_move(c2['default_journal_bank'], '2017-06-01', [
            (c2['default_account_expense'], 400.0, 0.0),
            (c2['default_account_revenue'], 0.0, 400.0),
        ])
        (cls.move_2016_1 + cls.move_2016_2 + cls.move_2017_1 + cls.move_2017_2).action_post()

        cls.native = cls.env.ref('account_reports.trial_balance_report')
        cls.report = cls.env.ref('azk_dynamic_trial_balance.dynamic_trial_balance_report')
        cls.company_data['company'].totals_below_sections = False

    @classmethod
    def _azk_move(cls, journal, date, lines, state_post=False):
        """Create an entry; ``lines`` is a list of (account, debit, credit)."""
        return cls.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.from_string(date),
            'journal_id': journal.id,
            'line_ids': [
                (0, 0, {'name': f'{date}-{i}', 'account_id': account.id, 'debit': debit, 'credit': credit})
                for i, (account, debit, credit) in enumerate(lines)
            ],
        })

    def _options(self, report, date_from, date_to, **extra):
        return self._generate_options(report, date_from, date_to, default_options=extra or None)

    def _line_key(self, report, line):
        markup = report._get_markup(line.id)
        if markup == 'undistributed_profits_losses':
            return f"UNDISTRIBUTED:{report._get_res_id_from_line_id(line.id, 'res.company')}"
        if markup == 'cumulative_translation_adjustment':
            return 'CTA'
        if markup == 'parent_account':
            return f"PARENT:{report._get_res_id_from_line_id(line.id, 'account.account')}"
        account_id = report._get_res_id_from_line_id(line.id, 'account.account')
        if markup == 'azk_currency':
            return f"{account_id}:{report._get_res_id_from_line_id(line.id, 'res.currency')}"
        if account_id:
            return account_id
        return 'TOTAL' if line.name == 'Total' else line.name

    def _tb_values(self, report, options, lines=None):
        """Return {line_key: {init_balance, debit, credit, period_balance, end_balance}} for one period."""
        lines = report._get_lines(options) if lines is None else lines
        result = {}
        for line in lines:
            sections = {}
            for column in line.columns:
                if column.column_group_index is None:
                    continue
                col_type = options['column_groups'][column.column_group_index]['forced_options']['trial_balance_column_type']
                value = column.no_format if isinstance(column.no_format, (int, float)) else 0.0
                sections.setdefault(col_type, {})[column.expression_label] = value
            def net(section):
                vals = sections.get(section, {})
                if 'balance' in vals and not ({'debit', 'credit'} <= vals.keys()):
                    return vals['balance']
                return vals.get('debit', 0.0) - vals.get('credit', 0.0)
            period = sections.get('period', {})
            result[self._line_key(report, line)] = {
                'init_balance': net('initial_balance'),
                'debit': period.get('debit', 0.0),
                'credit': period.get('credit', 0.0),
                'period_balance': period.get('debit', 0.0) - period.get('credit', 0.0),
                'end_balance': net('end_balance'),
                '_sections': sections,
            }
        return result

    def assertParity(self, ours, native, keys=VALUE_KEYS, msg=''):
        self.assertEqual(set(ours) - {'TOTAL'}, set(native) - {'TOTAL'}, f'line sets differ {msg}')
        for key, native_vals in native.items():
            for value_key in keys:
                self.assertAlmostEqual(
                    ours[key][value_key], native_vals[value_key], places=2,
                    msg=f'{key} / {value_key} {msg}',
                )
