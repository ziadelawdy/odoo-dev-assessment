import re
from collections import defaultdict

from odoo import _, api, models

SPLIT_SECTIONS = ('initial_balance', 'end_balance')
ACCOUNT_LEVEL_MARKUPS = ('undistributed_profits_losses', 'cumulative_translation_adjustment')
# Account prefixes are matched with '=like'; only plain code characters are
# accepted so '%' / '_' wildcards (or anything else) can never be injected.
PREFIX_RE = re.compile(r'^[0-9A-Za-z.]+$')
AZK_TB_DEFAULTS = {
    'journal_ids': [],
    'account_prefixes': [],
    'analytic_account_ids': [],
    'skip_zero_balance': False,
    'account_level': False,
    'show_amount_currency': False,
}
SUMMARY_WARNING = 'azk_dynamic_trial_balance.warning_filter_summary'
ANALYTIC_WARNING = 'azk_dynamic_trial_balance.warning_analytic_unbalanced'


class AzkDynamicTrialBalanceReportHandler(models.AbstractModel):
    """Custom handler of the Dynamic Trial Balance.

    Inherits the native Trial Balance handler so the opening balance, the
    fiscal-year logic for P&L accounts, the Undistributed Profits/Losses line
    and the company scoping are the native ones by construction.

    On top of it, Initial and End sections are presented as a classic trial
    balance: the net balance goes to Debit when positive, to Credit when
    negative, and Balance = Debit - Credit.
    """
    _name = 'azk.dynamic.trial.balance.report.handler'
    _inherit = ['account.trial.balance.report.handler']
    _description = 'Dynamic Trial Balance Custom Handler'

    @api.model
    def _display_single_column_for_initial_and_end_sections(self, options):
        # Always show Debit / Credit / Balance in the Initial and End sections.
        return False

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------
    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        azk_tb = self._azk_sanitize(previous_options.get('azk_tb') or {})
        options['azk_tb'] = azk_tb

        base_domain = list(options.get('forced_domain') or [])
        if azk_tb['journal_ids']:
            base_domain.append(('journal_id', 'in', azk_tb['journal_ids']))
        prefixes = azk_tb['account_prefixes']
        prefix_domain = ['|'] * (len(prefixes) - 1) + [
            ('account_id.code', '=like', f'{prefix}%') for prefix in prefixes
        ]
        options['azk_tb_domain_without_prefix'] = base_domain
        options['forced_domain'] = base_domain + prefix_domain

        if azk_tb['analytic_account_ids']:
            # Reuse the engine's analytic shadow table: amounts come from the
            # analytic lines, i.e. only the share distributed to the account.
            options['analytic_groupby_option'] = True
            options['analytic_accounts_list'] = tuple(azk_tb['analytic_account_ids'])

    @api.model
    def _azk_sanitize(self, raw):
        def int_list(values):
            return [int(v) for v in values or [] if isinstance(v, int) or (isinstance(v, str) and v.isdigit())]

        prefixes = []
        for prefix in raw.get('account_prefixes') or []:
            prefix = str(prefix).strip()
            if PREFIX_RE.match(prefix) and prefix not in prefixes:
                prefixes.append(prefix)
        level = raw.get('account_level')
        level = int(level) if str(level).isdigit() and 1 <= int(level) <= 5 else False
        return {
            **AZK_TB_DEFAULTS,
            'journal_ids': int_list(raw.get('journal_ids')),
            'account_prefixes': prefixes,
            'analytic_account_ids': int_list(raw.get('analytic_account_ids')),
            'skip_zero_balance': bool(raw.get('skip_zero_balance')),
            'account_level': level,
            'show_amount_currency': bool(raw.get('show_amount_currency')),
        }

    # ------------------------------------------------------------------
    # Warnings (on-screen filter summary and analytic notice)
    # ------------------------------------------------------------------
    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)
        azk_tb = options.get('azk_tb') or {}
        summary = self._azk_filter_summary(azk_tb)
        if summary:
            warnings[SUMMARY_WARNING] = {'summary': summary, 'alert_type': 'info'}
        if azk_tb.get('analytic_account_ids'):
            warnings[ANALYTIC_WARNING] = {'alert_type': 'warning'}

    @api.model
    def _azk_filter_summary(self, azk_tb):
        parts = []
        if azk_tb.get('journal_ids'):
            journals = self.env['account.journal'].browse(azk_tb['journal_ids']).exists()
            parts.append(_('Journals: %s', ', '.join(journals.mapped('name'))))
        if azk_tb.get('account_prefixes'):
            parts.append(_('Account prefixes: %s', ', '.join(azk_tb['account_prefixes'])))
        if azk_tb.get('analytic_account_ids'):
            analytics = self.env['account.analytic.account'].browse(azk_tb['analytic_account_ids']).exists()
            parts.append(_('Analytic accounts: %s', ', '.join(analytics.mapped('name'))))
        if azk_tb.get('account_level'):
            parts.append(_('Hierarchy up to level %s', azk_tb['account_level']))
        if azk_tb.get('skip_zero_balance'):
            parts.append(_('Zero balances skipped'))
        if azk_tb.get('show_amount_currency'):
            parts.append(_('Amount in currency shown'))
        return ' | '.join(parts)

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        if not lines:
            return lines
        if (options.get('azk_tb') or {}).get('account_prefixes'):
            lines = self._azk_apply_prefixes_to_earnings_lines(report, options, lines)

        # The native postprocessor moves the report total to the end and tags
        # its id with the 'total' markup; sub-line expansions have no total.
        total_line = lines[-1] if report._get_markup(lines[-1].id) == 'total' else None
        for line in lines:
            if line is not total_line:
                self._azk_split_line(options, line)

        if total_line is not None:
            account_level_lines = [
                line for line in lines
                if line is not total_line and self._azk_is_account_level(report, line)
            ]
            self._azk_split_total_line(options, total_line, account_level_lines)
        return lines

    def _azk_apply_prefixes_to_earnings_lines(self, report, options, lines):
        """Undistributed Profits/Losses (and CTA) belong conceptually to the
        company's unaffected-earnings account. With an account-prefix filter:
        - they are dropped unless a prefix matches that account's code;
        - when kept, they are recomputed without the prefix restriction, since
          they aggregate P&L accounts that the prefix would otherwise exclude.
        """
        prefixes = options['azk_tb']['account_prefixes']
        earnings_markups = ACCOUNT_LEVEL_MARKUPS
        matched_companies = set()
        for company_id in report.get_report_company_ids(options):
            company = self.env['res.company'].browse(company_id)
            unaffected = self.env['account.account'].with_company(company).search([
                ('account_type', '=', 'equity_unaffected'),
                *self.env['account.account']._check_company_domain(company),
            ], limit=1)
            if unaffected and unaffected.code and unaffected.code.startswith(tuple(prefixes)):
                matched_companies.add(company_id)

        kept = [line for line in lines if report._get_markup(line.id) not in earnings_markups]
        if not matched_companies:
            return kept

        unfiltered = {**options, 'forced_domain': options['azk_tb_domain_without_prefix']}
        recomputed = report._get_unallocated_earnings_lines(unfiltered, 'strict_range', auditable=True)
        if report.currency_translation == 'cta':
            cta_line = report._compute_cumulative_translation_adjustment_lines(unfiltered, 'strict_range')
            recomputed += [cta_line] if cta_line else []
        recomputed = [
            line for line in recomputed
            if report._get_res_id_from_line_id(line.id, 'res.company') in matched_companies
            or report._get_markup(line.id) == 'cumulative_translation_adjustment'
        ]
        total_index = len(kept) - 1 if kept and report._get_markup(kept[-1].id) == 'total' else len(kept)
        return kept[:total_index] + recomputed + kept[total_index:]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _azk_is_account_level(self, report, line):
        """True for the lines that carry an account balance: accounts (not
        hierarchy parents), Undistributed Profits/Losses and the CTA line."""
        markup = report._get_markup(line.id)
        if markup in ACCOUNT_LEVEL_MARKUPS:
            return True
        if markup == 'parent_account':
            return False
        return bool(report._get_res_id_from_line_id(line.id, 'account.account'))

    @api.model
    def _azk_columns_by_block(self, options, line):
        """{block_key: {column_type: {expression_label: column}}}"""
        blocks = defaultdict(lambda: defaultdict(dict))
        for column in line.columns:
            if column.column_group_index is None:
                continue
            group = options['column_groups'][column.column_group_index]
            forced = group['forced_options']
            block_key = (
                forced.get('trial_balance_column_block_id'),
                tuple(sorted(group.get('horizontal_groupby_element', {}).items())),
            )
            blocks[block_key][forced.get('trial_balance_column_type')][column.expression_label] = column
        return blocks

    @staticmethod
    def _azk_value(column):
        return column.no_format if column and isinstance(column.no_format, (int, float)) else 0.0

    @classmethod
    def _azk_net(cls, columns):
        if 'debit' in columns or 'credit' in columns:
            return cls._azk_value(columns.get('debit')) - cls._azk_value(columns.get('credit'))
        return cls._azk_value(columns.get('balance'))

    @staticmethod
    def _azk_set(column, value):
        if column is not None:
            column.no_format = value
            column.is_zero = not bool(value)

    @classmethod
    def _azk_write_section(cls, columns, debit, credit):
        cls._azk_set(columns.get('debit'), debit)
        cls._azk_set(columns.get('credit'), credit)
        cls._azk_set(columns.get('balance'), debit - credit)

    @classmethod
    def _azk_split_net(cls, columns, net):
        cls._azk_write_section(columns, max(net, 0.0), max(-net, 0.0))

    def _azk_split_line(self, options, line):
        for sections in self._azk_columns_by_block(options, line).values():
            initial, period = sections.get('initial_balance', {}), sections.get('period', {})
            initial_net = self._azk_net(initial)
            period_net = self._azk_net(period)
            # End is recomputed here: the native postprocessor sums every
            # Initial column into its debit total, which double counts once the
            # Initial section carries Debit, Credit and Balance columns.
            self._azk_set(period.get('balance'), period_net)
            self._azk_split_net(initial, initial_net)
            self._azk_split_net(sections.get('end_balance', {}), initial_net + period_net)

    def _azk_split_total_line(self, options, total_line, account_level_lines):
        """The grand total sums the account-level split columns, so that total
        debit balances and total credit balances are both visible."""
        sums = defaultdict(lambda: defaultdict(float))
        for line in account_level_lines:
            for block_key, sections in self._azk_columns_by_block(options, line).items():
                for section in SPLIT_SECTIONS:
                    for label in ('debit', 'credit'):
                        sums[(block_key, section)][label] += self._azk_value(sections.get(section, {}).get(label))

        for block_key, sections in self._azk_columns_by_block(options, total_line).items():
            period = sections.get('period', {})
            self._azk_set(period.get('balance'), self._azk_net(period))
            for section in SPLIT_SECTIONS:
                totals = sums[(block_key, section)]
                self._azk_write_section(sections.get(section, {}), totals['debit'], totals['credit'])
