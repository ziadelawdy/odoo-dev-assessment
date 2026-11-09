from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.trial_balance_handler import PREFIX_RE

LEVELS = [(str(level), str(level)) for level in range(1, 6)]


class AzkDynamicTrialBalanceWizard(models.TransientModel):
    _name = 'azk.dynamic.trial.balance.wizard'
    _description = 'Dynamic Trial Balance'

    date_from = fields.Date(string='Start Date', required=True, default=lambda self: self._default_date_from())
    date_to = fields.Date(string='End Date', required=True, default=fields.Date.context_today)

    # Options
    posted_entries = fields.Boolean(string='Posted Entries', default=True, readonly=True)
    include_unposted = fields.Boolean(
        string='Include Unposted Entries',
        help='Draft entries are included in the report; cancelled entries never are.',
    )
    hierarchy_subtotals = fields.Boolean(
        string='Hierarchy and Subtotals', default=True,
        help='Show the parent-account tree with subtotals.',
    )
    hierarchy_only_parents = fields.Boolean(string='Hierarchy Only Parents')
    account_level = fields.Selection(LEVELS, string='Account Level Up To', default='1')

    # Filters
    account_prefixes = fields.Char(
        string='Accounts',
        help='Specify the account prefix to view only matching accounts. '
             'If no prefix is entered, all accounts will be displayed.',
    )
    journal_ids = fields.Many2many(
        'account.journal', string='Journals',
        check_company=True,
        help='Select specific journals to include in the report, or leave the field empty to include all journals.',
    )
    analytic_account_ids = fields.Many2many(
        'account.analytic.account', string='Analytic Accounts',
        help='Select specific analytic accounts to include in the report, or leave the field empty to include all.',
    )
    skip_zero_balance = fields.Boolean(
        string='Skip Zero Balance',
        help='Select this option to hide accounts that have neither an initial balance nor any transactions in this report.',
    )
    show_amount_currency = fields.Boolean(
        string='Show Amount Currency',
        help='Enable this option to group the report by Account, followed by Amount Currency. '
             'This will show the sum of the Amount Currency for each account in its respective currency. '
             'Essentially, this option provides a breakdown of account balances by the transaction currency used.',
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    @api.model
    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return self.env.company.compute_fiscalyear_dates(today)['date_from']

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_('The start date must be before the end date.'))

    @api.constrains('account_prefixes')
    def _check_account_prefixes(self):
        for wizard in self:
            invalid = [p for p in wizard._azk_prefix_list() if not PREFIX_RE.match(p)]
            if invalid:
                raise ValidationError(_(
                    'Invalid account prefix: %s. Use the beginning of account codes '
                    '(letters, digits, "." and "-"), separated by commas.', ', '.join(invalid),
                ))

    def _azk_prefix_list(self):
        self.ensure_one()
        return [p.strip() for p in (self.account_prefixes or '').split(',') if p.strip()]

    @api.constrains('analytic_account_ids')
    def _check_analytic_single_plan(self):
        for wizard in self:
            if len(wizard.analytic_account_ids.root_plan_id) > 1:
                raise ValidationError(_(
                    'Select analytic accounts from a single analytic plan: each plan distributes '
                    '100%% of an entry on its own, so mixing plans would count amounts twice.'
                ))

    def _report(self):
        return self.env.ref('azk_dynamic_trial_balance.dynamic_trial_balance_report')

    def _azk_tb_values(self):
        self.ensure_one()
        return {
            'account_prefixes': self._azk_prefix_list(),
            'analytic_account_ids': self.analytic_account_ids.ids,
            'skip_zero_balance': self.skip_zero_balance,
            'account_level': int(self.account_level) if self.hierarchy_only_parents and self.account_level else False,
            'show_amount_currency': self.show_amount_currency,
        }

    def _build_report_options(self):
        """Report options for the wizard's selection; the wizard-only filters
        travel under 'azk_tb' and are re-applied by the report handler."""
        self.ensure_one()
        report = self._report()
        return report.get_options({
            'selected_variant_id': report.id,
            'date': {
                'date_from': fields.Date.to_string(self.date_from),
                'date_to': fields.Date.to_string(self.date_to),
                'mode': 'range',
                'filter': 'custom',
            },
            'all_entries': self.include_unposted,
            'hierarchy': self.hierarchy_subtotals or self.hierarchy_only_parents,
            'unfold_all': False,
            'azk_tb': self._azk_tb_values(),
            # journals use the native report journal filter (editable in the report)
            'journals': [{'id': journal_id, 'selected': True} for journal_id in self.journal_ids.ids],
        })

    def action_preview(self):
        options = self._build_report_options()
        return {
            'type': 'ir.actions.client',
            'name': _('Dynamic Trial Balance'),
            'tag': 'account_report',
            'context': {'report_id': options['report_id']},
            'params': {'options': options, 'ignore_session': True},
        }

    def action_pdf(self):
        options = self._build_report_options()
        return self._report().export_file(options, 'export_to_pdf')

    def action_xlsx(self):
        options = self._build_report_options()
        return self._report().export_file(options, 'export_to_xlsx')
