from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

DEMO_REF = 'AZK-DTB-DEMO'

# code, name, account_type, parent code
DEMO_ACCOUNTS = [
    ('1000', 'Current Assets (Demo)', 'asset_current', None),
    ('1100', 'Cash and Banks (Demo)', 'asset_cash', '1000'),
    ('1110', 'Main Bank (Demo)', 'asset_cash', '1100'),
    ('1120', 'Petty Cash (Demo)', 'asset_cash', '1100'),
    ('1200', 'Customers (Demo)', 'asset_receivable', '1000'),
    ('3000', 'Equity (Demo)', 'equity', None),
    ('3100', 'Share Capital (Demo)', 'equity', '3000'),
    ('4000', 'Revenue (Demo)', 'income', None),
    ('4100', 'Product Sales (Demo)', 'income', '4000'),
    ('6000', 'Operating Expenses (Demo)', 'expense', None),
    ('6100', 'Salaries (Demo)', 'expense', '6000'),
    ('6200', 'Rent (Demo)', 'expense', '6000'),
]


class AzkDynamicTrialBalanceDemo(models.AbstractModel):
    _inherit = 'azk.dynamic.trial.balance.report.handler'

    @api.model
    def _azk_create_demo_data(self):
        """Demo data for evaluating the Dynamic Trial Balance (loaded from
        demo/demo_data.xml): a 3-level account tree, two foreign currencies,
        a 60/40 analytic distribution, entries over two fiscal years, and a
        draft and a cancelled entry. Idempotent."""
        company = self.env.company
        Move = self.env['account.move']
        if Move.search_count([('ref', '=like', f'{DEMO_REF}%'), ('company_id', '=', company.id)], limit=1):
            return False

        accounts = self._azk_demo_accounts(company)
        foreign = self._azk_demo_currencies(company)
        plan = self.env['account.analytic.plan'].create({'name': 'Departments (Demo)'})
        sales_dept = self.env['account.analytic.account'].create({'name': 'Sales Dept (Demo)', 'plan_id': plan.id, 'company_id': company.id})
        admin_dept = self.env['account.analytic.account'].create({'name': 'Admin Dept (Demo)', 'plan_id': plan.id, 'company_id': company.id})

        journal_domain = self.env['account.journal']._check_company_domain(company)
        misc = self.env['account.journal'].search([('type', '=', 'general'), *journal_domain], limit=1)
        sale = self.env['account.journal'].search([('type', '=', 'sale'), *journal_domain], limit=1) or misc

        current_start = company.compute_fiscalyear_dates(fields.Date.context_today(self))['date_from']
        previous_start = current_start - relativedelta(years=1)
        eur, gbp = foreign[0], foreign[1]

        def line(code, debit, credit, currency=None, amount_currency=None, analytic=None):
            vals = {'name': accounts[code].name, 'account_id': accounts[code].id, 'debit': debit, 'credit': credit}
            if currency:
                vals.update(currency_id=currency.id, amount_currency=amount_currency)
            if analytic:
                vals['analytic_distribution'] = analytic
            return (0, 0, vals)

        def move(number, journal, date, lines):
            return Move.create({
                'move_type': 'entry', 'ref': f'{DEMO_REF}-{number:02d}', 'journal_id': journal.id,
                'date': date, 'company_id': company.id, 'line_ids': lines,
            })

        posted = (
            # previous fiscal year
            move(1, misc, previous_start, [line('1110', 50000, 0), line('3100', 0, 50000)])
            | move(2, sale, previous_start + relativedelta(months=3), [line('1200', 12000, 0), line('4100', 0, 12000)])
            | move(3, misc, previous_start + relativedelta(months=5), [line('6200', 3000, 0), line('1110', 0, 3000)])
            # current fiscal year
            | move(4, misc, current_start + relativedelta(months=1), [
                line('6100', 8000, 0, analytic={str(sales_dept.id): 60, str(admin_dept.id): 40}),
                line('1110', 0, 8000),
            ])
            | move(5, sale, current_start + relativedelta(months=2), [
                line('1200', 1100, 0, eur, 1000.0), line('4100', 0, 1100, eur, -1000.0),
            ])
            | move(6, misc, current_start + relativedelta(months=2, days=10), [
                line('1120', 500, 0, gbp, 400.0), line('1110', 0, 500, gbp, -400.0),
            ])
        )
        posted.action_post()
        move(7, misc, current_start + relativedelta(months=3), [line('6200', 1000, 0), line('1110', 0, 1000)])  # draft
        cancelled = move(8, sale, current_start + relativedelta(months=3), [line('1200', 9999, 0), line('4100', 0, 9999)])
        cancelled.button_cancel()
        return True

    @api.model
    def _azk_demo_accounts(self, company):
        Account = self.env['account.account'].with_company(company)
        accounts = {}
        for code, name, account_type, parent_code in DEMO_ACCOUNTS:
            account = Account.search([('code', '=', code), *Account._check_company_domain(company)], limit=1)
            if not account:
                account = Account.create({
                    'code': code,
                    'name': name,
                    'account_type': account_type,
                    'reconcile': account_type == 'asset_receivable',
                    'parent_id': accounts[parent_code].id if parent_code else False,
                    'company_ids': [(6, 0, company.ids)],
                })
            accounts[code] = account
        return accounts

    @api.model
    def _azk_demo_currencies(self, company):
        """Two active foreign currencies with a rate on the company."""
        rates = {'EUR': 0.9, 'GBP': 0.8, 'CAD': 1.35}
        currencies = self.env['res.currency'].with_context(active_test=False).search([
            ('name', 'in', list(rates)), ('id', '!=', company.currency_id.id),
        ], order='name desc')[:2]
        for currency in currencies:
            currency.active = True
            if not currency.rate_ids.filtered(lambda r: r.company_id == company):
                self.env['res.currency.rate'].create({
                    'currency_id': currency.id, 'company_id': company.id,
                    'name': '2000-01-01', 'rate': rates[currency.name],
                })
        return currencies
