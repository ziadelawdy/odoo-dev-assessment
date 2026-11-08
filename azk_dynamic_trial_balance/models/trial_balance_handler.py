from collections import defaultdict

from odoo import api, models

SPLIT_SECTIONS = ('initial_balance', 'end_balance')
ACCOUNT_LEVEL_MARKUPS = ('undistributed_profits_losses', 'cumulative_translation_adjustment')


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

    def _custom_line_postprocessor(self, report, options, lines):
        lines = super()._custom_line_postprocessor(report, options, lines)
        if not lines:
            return lines

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
