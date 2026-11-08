import dataclasses
import re
from collections import defaultdict

from odoo import _, api, models
from odoo.tools import SQL

SPLIT_SECTIONS = ('initial_balance', 'end_balance')
ACCOUNT_LEVEL_MARKUPS = ('undistributed_profits_losses', 'cumulative_translation_adjustment')
# Account prefixes are matched with '=like'; only the characters Odoo allows in
# account codes (account.account ACCOUNT_CODE_REGEX: letters, digits, '.', '-')
# are accepted, so the '%' / '_' wildcards can never be injected.
PREFIX_RE = re.compile(r'^[0-9A-Za-z.\-]+$')
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


class _RowShiftedSheet:
    """Worksheet proxy that moves every write ``offset`` rows down, so the
    native XLSX writer (which always starts at row 0) renders below our
    header. Only the methods used by the native writer are shifted."""

    def __init__(self, sheet, offset):
        self._sheet = sheet
        self._offset = offset

    def write(self, row, col, *args, **kwargs):
        return self._sheet.write(row + self._offset, col, *args, **kwargs)

    def write_datetime(self, row, col, *args, **kwargs):
        return self._sheet.write_datetime(row + self._offset, col, *args, **kwargs)

    def merge_range(self, first_row, first_col, last_row, last_col, *args, **kwargs):
        return self._sheet.merge_range(first_row + self._offset, first_col, last_row + self._offset, last_col, *args, **kwargs)

    def __getattr__(self, name):
        # set_column and anything row-independent go straight to the sheet
        return getattr(self._sheet, name)


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
        # Multi-company "consolidation" regroups lines by account code (the
        # accounts become hidden sub-lines). Every feature of this report works
        # on real account lines, so each company's accounts are listed instead.
        options['show_consolidation'] = False
        options['consolidation'] = False

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

        self._azk_init_amount_currency_column(options, azk_tb['show_amount_currency'])

        # PDF header: native filters + period, wizard filters and analytic notice
        pdf_templates = options.setdefault('custom_display_config', {}).setdefault('pdf_export', {})
        pdf_templates['pdf_export_filters'] = 'azk_dynamic_trial_balance.pdf_export_filters'

    @api.model
    def _azk_init_amount_currency_column(self, options, show):
        """Amount Currency is a single column, in the End section, and only
        when the option is enabled."""
        def column_type(column):
            group = options['column_groups'][column['column_group_index']]
            return group['forced_options'].get('trial_balance_column_type')

        options['columns'] = [
            column for column in options['columns']
            if column['expression_label'] != 'amount_currency' or (show and column_type(column) == 'end_balance')
        ]
        if show and len(options['column_headers']) == 1:
            # Sections no longer have the same number of columns: give each
            # header its own colspan (as the native Initial/End headers do).
            for index, header in enumerate(options['column_headers'][0]):
                header['colspan'] = sum(1 for column in options['columns'] if column['column_group_index'] == index)

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------
    def _report_engine_trial_balance(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """Same as the native engine (account_trial_balance_report.py) with an
        extra ``amount_currency`` aggregate, needed for "Show Amount Currency".
        The native engine builds its SELECT inline, so it cannot be extended
        through super()."""
        report = self.env['account.report'].browse(options['report_id'])
        current_groupbys = [current_groupby] if current_groupby and not isinstance(current_groupby, list) else current_groupby or []
        report._check_groupby_fields(current_groupbys)
        result_key = next(iter(formulas_dict.values()))
        empty = {'balance': 0.0, 'debit': 0.0, 'credit': 0.0, 'amount_currency': 0.0}

        if 'id' in current_groupbys and options['trial_balance_column_type'] == 'initial_balance':
            return {result_key: []}
        if options['trial_balance_column_type'] == 'end_balance':
            return {result_key: [] if current_groupbys else {**empty, 'has_sublines': True}}

        extra_domain = []
        if fiscalyear_start := options.get('trial_balance_block_fiscalyear_start'):
            extra_domain = [
                '|',
                ('account_id.include_initial_balance', '=', True),
                ('date', '>=', fiscalyear_start),
            ]
        if options.get('export_mode') == 'print' and options.get('filter_search_bar'):
            extra_domain.append(('account_id', 'ilike', options['filter_search_bar']))

        block_end_date = None
        if options['trial_balance_column_type'] == 'initial_balance':
            date_scope = 'from_beginning'
            block_end_date = options.get('trial_balance_block_end_date')

        query = report._get_report_query(options, date_scope, domain=extra_domain, cta_date_to=block_end_date)
        select_groupby = SQL()
        if current_groupbys:
            select_groupby = SQL(',\n').join(
                SQL("%s AS %s",
                    self.env['account.move.line']._field_to_sql("account_move_line", groupby_key, query),
                    SQL.identifier(f'groupby_key_{groupby_key}'))
                for groupby_key in current_groupbys
            )
            query.groupby = SQL(',').join(SQL.identifier(f'groupby_key_{groupby_key}') for groupby_key in current_groupbys)

        query_results = self.env.execute_query_dict(query.select(SQL(', ').join(s for s in (
            select_groupby,
            SQL('COALESCE(SUM(%s), 0.0) AS balance', query.table.consolidation_balance),
            SQL('COALESCE(SUM(%s), 0.0) AS credit', query.table.consolidation_credit),
            SQL('COALESCE(SUM(%s), 0.0) AS debit', query.table.consolidation_debit),
            SQL('COALESCE(SUM(%s), 0.0) AS amount_currency', query.table.amount_currency),
        ) if s)))

        if not current_groupbys:
            if not query_results:
                return {result_key: {**empty, 'has_sublines': False}}
            return {result_key: {**query_results[0], 'has_sublines': True}}

        return {result_key: [
            (
                result[f'groupby_key_{current_groupbys[0]}']
                if len(current_groupbys) == 1
                else tuple(result[f'groupby_key_{groupby}'] for groupby in current_groupbys),
                {**result, 'has_sublines': True},
            )
            for result in query_results
        ]}

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
    # XLSX export
    # ------------------------------------------------------------------
    def _inject_report_into_xlsx_sheet(self, options, workbook):
        """Hook called by account.report.export_to_xlsx for custom handlers.

        The native sheet has no header (no company, period or filters), so we
        write one, then let the native writer render the table below it, which
        keeps its formatting (numeric cells, indentation, bold totals)."""
        report = self.env['account.report'].browse(options['report_id'])
        sheet = workbook.add_worksheet(report.name[:31])
        title = workbook.add_format({'font_name': 'Lato', 'font_size': 14, 'bold': True})
        text = workbook.add_format({'font_name': 'Lato', 'font_size': 11})
        warning = workbook.add_format({'font_name': 'Lato', 'font_size': 11, 'bold': True, 'font_color': '#B45309'})

        header = [(report.name, title)]
        header += [(text_line, text) for text_line in self._azk_export_header_lines(options)]
        if (options.get('azk_tb') or {}).get('analytic_account_ids'):
            header.append((self._azk_analytic_notice(), warning))
        for row, (value, style) in enumerate(header):
            sheet.write(row, 0, value, style)

        report._inject_report_into_xlsx_sheet(options, workbook, _RowShiftedSheet(sheet, len(header) + 1))

    @api.model
    def _azk_export_header_lines(self, options):
        companies = ', '.join(company['name'] for company in options.get('companies', []))
        lines = [
            _('Company: %s', companies) if companies else None,
            _('Period: %(date_from)s - %(date_to)s', date_from=options['date']['date_from'], date_to=options['date']['date_to']),
            _('Unposted entries included') if options.get('all_entries') else None,
        ]
        summary = self._azk_filter_summary(options.get('azk_tb') or {})
        if summary:
            lines.append(_('Filters: %s', summary))
        return [line for line in lines if line]

    @api.model
    def _azk_analytic_notice(self):
        return _(
            'Analytic filter applied: only the amounts distributed to the selected analytic accounts are '
            'reported; accounts without analytic distribution are excluded, so this report is not balanced.'
        )

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    def _custom_line_postprocessor(self, report, options, lines):
        # Same check as the native handler: the full report render starts with
        # the root report line; expansions of a single line (get_expanded_lines)
        # must not receive report-level lines such as Undistributed P/L.
        is_report_render = bool(lines) and report._parse_line_id(lines[0].id)[-1] == (
            '', 'account.report.line', report.line_ids[0].id,
        )
        lines = super()._custom_line_postprocessor(report, options, lines)
        if not lines:
            return lines
        azk_tb = options.get('azk_tb') or {}
        if is_report_render and azk_tb.get('account_prefixes'):
            lines = self._azk_apply_prefixes_to_earnings_lines(report, options, lines)
        if is_report_render and azk_tb.get('show_amount_currency'):
            lines = self._azk_split_lines_by_currency(report, options, lines)

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

        azk_tb = options.get('azk_tb') or {}
        if azk_tb.get('skip_zero_balance'):
            lines = self._azk_skip_zero_lines(report, options, lines)
        if azk_tb.get('account_level') and options.get('hierarchy'):
            lines = self._azk_limit_hierarchy_level(report, lines, azk_tb['account_level'])
        return lines

    def _azk_skip_zero_lines(self, report, options, lines):
        """Hide account-level lines whose initial balance, period debit,
        period credit and end balance are all zero (an account whose
        movements cancel out is kept), then parents left without children."""
        def is_zero(line):
            for sections in self._azk_columns_by_block(options, line).values():
                values = (
                    self._azk_net(sections.get('initial_balance', {})),
                    self._azk_value(sections.get('period', {}).get('debit')),
                    self._azk_value(sections.get('period', {}).get('credit')),
                    self._azk_net(sections.get('end_balance', {})),
                )
                if any(abs(value) > 1e-9 for value in values):
                    return False
            return True

        kept = [
            line for line in lines
            if not (self._azk_is_account_level(report, line) and is_zero(line))
        ]
        return self._azk_drop_childless_parents(report, kept)

    @api.model
    def _azk_drop_childless_parents(self, report, lines):
        while True:
            parent_ids = {line.parent_id for line in lines if line.parent_id}
            kept = [
                line for line in lines
                if report._get_markup(line.id) != 'parent_account' or line.id in parent_ids
            ]
            if len(kept) == len(lines):
                return kept
            lines = kept

    @api.model
    def _azk_hierarchy_depth(self, report, line):
        """Depth in the account tree: 1 for top-level accounts/parents."""
        parsed = report._parse_line_id(line.id)
        parents = sum(1 for markup, _model, _value in parsed if markup == 'parent_account')
        return parents if report._get_markup(line.id) == 'parent_account' else parents + 1

    def _azk_limit_hierarchy_level(self, report, lines, level):
        """Keep the tree down to ``level``; deeper lines are already included
        in their ancestors' subtotals, so totals do not change."""
        kept = []
        for line in lines:
            depth = self._azk_hierarchy_depth(report, line)
            if depth > level:
                continue
            if depth == level and report._get_markup(line.id) == 'parent_account':
                line.unfoldable = False
                line.unfolded = False
            kept.append(line)
        return kept

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

    def _azk_split_lines_by_currency(self, report, options, lines):
        """Replace every account line by one line per transaction currency.
        Their company-currency figures add up to the account's; the Amount
        Currency column (End section) shows the end balance in that currency.
        Lines aggregating several currencies (parents, earnings, total) keep
        their Amount Currency cell empty."""
        groupby = ['account_id', 'currency_id']
        data = defaultdict(dict)  # {(account_id, currency_id): {column_group_index: values}}
        for group_index, group_options in report._split_options_per_column_group(options).items():
            if group_options.get('trial_balance_column_type') not in ('initial_balance', 'period'):
                continue
            result = self._report_engine_trial_balance(group_options, 'strict_range', {'azk': 'azk'}, groupby)
            for (account_id, currency_id), values in result['azk']:
                data[(account_id, currency_id)][group_index] = values

        currencies_by_account = defaultdict(list)
        for account_id, currency_id in sorted(data):
            currencies_by_account[account_id].append(currency_id)

        new_lines = []
        replaced_ids = set()
        for line in lines:
            if line.parent_id in replaced_ids:
                # sub-lines (partner, journal item...) of an account that is now
                # shown per currency: their parent line no longer exists
                replaced_ids.add(line.id)
                continue
            account_id = report._get_res_id_from_line_id(line.id, 'account.account')
            markup = report._get_markup(line.id)
            is_account_line = report._parse_line_id(line.id)[-1][1] == 'account.account' and markup != 'parent_account'
            if not is_account_line or account_id not in currencies_by_account:
                for column in line.columns:
                    if column.expression_label == 'amount_currency':
                        column.no_format = None
                        column.is_zero = True
                new_lines.append(line)
                continue
            replaced_ids.add(line.id)
            for currency_id in currencies_by_account[account_id]:
                new_lines.append(self._azk_currency_line(report, options, line, currency_id, data[(account_id, currency_id)]))
        return new_lines

    def _azk_currency_line(self, report, options, account_line, currency_id, values_by_group):
        currency = self.env['res.currency'].browse(currency_id)
        line_id = report._build_subline_id(
            account_line.id, report._build_line_id([('azk_currency', 'res.currency', currency_id)])
        )
        end_amount_currency = sum(values.get('amount_currency', 0.0) for values in values_by_group.values())
        columns = []
        for column in account_line.columns:
            column = dataclasses.replace(column, format_params=dataclasses.replace(column.format_params), name='')
            if column.column_group_index is not None:
                column_type = options['column_groups'][column.column_group_index]['forced_options'].get('trial_balance_column_type')
                if column.expression_label == 'amount_currency':
                    value = end_amount_currency if column_type == 'end_balance' else None
                    column.currency = currency
                    column.format_params.currency_id = currency.id
                    if value is not None and options.get('export_mode') != 'file':
                        # Odoo prints currency symbols only for multi-currency
                        # users; a foreign amount always needs its own symbol.
                        column.name = report._format_value(
                            {**options, 'multi_currency': True}, value, 'monetary', column.format_params,
                        )
                else:
                    value = values_by_group.get(column.column_group_index, {}).get(column.expression_label, 0.0)
                column.no_format = value
                column.is_zero = not value
            columns.append(column)
        return dataclasses.replace(
            account_line,
            id=line_id,
            name=f'{account_line.name} ({currency.name})',
            columns=columns,
            unfoldable=False,
            unfolded=False,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @api.model
    def _azk_is_account_level(self, report, line):
        """True for the lines that carry an account balance: accounts (not
        hierarchy parents), Undistributed Profits/Losses and the CTA line."""
        markup = report._get_markup(line.id)
        if markup in ACCOUNT_LEVEL_MARKUPS or markup == 'azk_currency':
            return True
        # hierarchy parents, and the section totals added below them when the
        # company uses "totals below sections" (their id embeds the account)
        if markup in ('parent_account', 'total'):
            return False
        # Only the account line itself: sub-lines of an unfolded account
        # (partner, journal item...) also embed the account id in their path.
        return report._parse_line_id(line.id)[-1][1] == 'account.account'

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
