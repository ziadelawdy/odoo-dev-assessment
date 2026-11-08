# Dynamic Trial Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Odoo 20 module `azk_dynamic_trial_balance`: a wizard-driven trial balance with
Initial, Movement and End sections, each showing Debit, Credit and Balance. It has Preview,
PDF and XLSX outputs, and its numbers match the native Odoo Trial Balance account by account.

**Architecture:**
- The module adds its own `account.report` record. Its custom handler inherits
  `account.trial.balance.report.handler`, so it reuses the native engine: fiscal-year
  logic, Undistributed Profits/Losses, company scoping and access check.
- Wizard-only options live under one options key, `azk_tb`. They are applied as
  `forced_domain` / analytic options and in the line postprocessor.
- Preview is the native report client action, opened with preset options.
- PDF and XLSX use the native `account.report` exporters on the same options.

**Tech Stack:** Odoo 20.0+e (`account_reports`), Python 3, QWeb, `account_reports.tests.common.TestAccountReportsCommon`, openpyxl 3.1.2 (tests only; already installed), xlsxwriter (used by native export).

**Spec:** `docs/superpowers/specs/2026-11-08-dynamic-trial-balance-design.md`

## Global Constraints

- Target Odoo `20.0+e-20261105` only. Before using any API, verify it in
  `C:\Program Files\Odoo 20.0e.20261105\server\odoo\addons`.
- Module name: `azk_dynamic_trial_balance`. Depends on: `account_reports`. License: `LGPL-3`.
- Never modify the native report `account_reports.trial_balance_report`. Our report is a
  separate record.
- No `sudo()` and no raw SQL outside the engine's `_get_report_query`.
- Classic split (§5.2):
  - Initial/End Debit = max(net, 0) and Credit = max(−net, 0).
  - Movement Debit/Credit are gross sums.
  - Balance = Debit − Credit.
- Parents are net-split. The grand total sums the account-level split columns (§11).
- Analytic filter:
  - Proportional share through the engine's analytic shadow table.
  - All selected analytic accounts must share one root plan.
  - A visible "report is not balanced" notice is shown.
- Unposted = draft only; cancelled entries are never included.
- Preview: the wizard-only options are read-only in the report and persist via `previous_options`.
- Tests run on a new database `azk_tb_test`. Never touch `noktest`, `nokasse` or `odoo20_dev`.
- Help texts: verbatim from spec §6.

**Test command** (from `C:\Users\ziad.elawdy\odoo-assessment`, PowerShell):

```
& "C:\Program Files\Odoo 20.0e.20261105\python\python.exe" "C:\Program Files\Odoo 20.0e.20261105\server\odoo-bin" -c odoo-dev.conf -d azk_tb_test -i azk_dynamic_trial_balance --test-tags /azk_dynamic_trial_balance --stop-after-init --log-level=test
```

- Use `-u` instead of `-i` once the module is installed.
- Narrow the run with `--test-tags /azk_dynamic_trial_balance:TestClass.test_name`.
- Pass = no `ERROR`/`FAIL` lines, and a `0 failed, 0 error(s)` summary.

## Review Focus

1. A P&L account whose earlier-year entries are dated just before the fiscal-year start.
   The initial balance must exclude them, and Undistributed P/L must carry them.
   *(Test: Task 2 `test_pl_account_across_fiscal_year`.)*
2. With the hierarchy on, parents must stay net-split while the grand total keeps
   debit-balances = credit-balances. Hierarchy roll-up can easily double count or re-split
   the total. *(Test: Task 2 `test_hierarchy_parent_net_and_total_gross`.)*
3. Re-rendering the Preview (unfold, date change) must not drop the `azk_tb` filters.
   Because `get_options` rebuilds the options from scratch, they could silently vanish.
   *(Test: Task 6 `test_options_survive_rerender`.)*
4. An account-prefix filter combined with Undistributed P/L: a prefix filter must not
   distort that line. *(Test: Task 3 `test_prefix_and_undistributed_line`.)*
5. Amount Currency with hierarchy and mixed currencies: parents must show no amount
   currency, and must never show a summed mix of currencies.
   *(Test: Task 5 `test_amount_currency_parent_blank`.)*

---

## File Structure

```
azk_dynamic_trial_balance/
├── __init__.py, __manifest__.py
├── data/dynamic_trial_balance_report.xml   # account.report record (columns + line + expressions)
├── models/__init__.py
├── models/trial_balance_handler.py         # handler inheriting the native TB handler
├── wizard/__init__.py
├── wizard/dynamic_trial_balance_wizard.py  # transient model + actions
├── wizard/dynamic_trial_balance_wizard_views.xml   # form + action + menu
├── security/ir.model.access.csv
├── demo/demo_data.xml                       # accounts tree, currencies, analytic, moves
├── tests/__init__.py
├── tests/common.py                          # shared fixture + helpers (parity comparison)
├── tests/test_report_engine.py              # Tasks 1–2
├── tests/test_report_filters.py             # Task 3
├── tests/test_report_display.py             # Tasks 4–5
├── tests/test_wizard.py                     # Task 6
└── tests/test_exports.py                    # Task 7
README.md, docs/genai/prompt-log.md          # Task 8 (repo root)
```

---

### Task 1: Module skeleton, report record, parity with native

**Files:**
- Create: `azk_dynamic_trial_balance/__init__.py`, `__manifest__.py`, `models/__init__.py`, `models/trial_balance_handler.py`, `data/dynamic_trial_balance_report.xml`, `security/ir.model.access.csv` (header only, until Task 6), `tests/__init__.py`, `tests/common.py`, `tests/test_report_engine.py`

**Interfaces:**
- Produces:
  - XML id `azk_dynamic_trial_balance.dynamic_trial_balance_report` (`account.report`).
  - Model `azk.dynamic.trial.balance.report.handler`, which inherits `account.trial.balance.report.handler`.
  - Columns `debit`, `credit`, `balance`; the `amount_currency` column comes in Task 5.
  - One line `TB` with custom-engine expressions `balance` / `debit` / `credit`. Their formula is `_report_engine_trial_balance`, same as `account_reports/data/trial_balance.xml`.
  - Report flags: `filter_multi_company=selector`, `filter_hierarchy=by_default`, `filter_show_draft=True`, `filter_unfold_all=True`, `search_bar=True`, `filter_journals=False`, `default_opening_date_filter=this_month`.
  - Test helper `AzkTBCommon(TestAccountReportsCommon)` in `tests/common.py` with:
    - `cls.report` (ours) and `cls.native` (`account_reports.trial_balance_report`)
    - `_tb_values(report, options) -> dict[str, dict]`, keyed by account code or `'UNDISTRIBUTED'` / `'TOTAL'`. Each value is `{'init_balance','debit','credit','period_balance','end_balance'}`, read from `line.columns` by `column_group` type (`trial_balance_column_type`) and `expression_label`.
    - `_options(report, date_from, date_to, **extra) -> dict`, which wraps `_generate_options`.
    - Fixture moves: the native test's 2016/2017 entries for two companies (copy the shape from `account_reports/tests/test_trial_balance_report.py:15-85`).

- [ ] **Step 1: Write failing test** `TestEngine.test_parity_with_native_unfiltered` (tag `post_install`, `-at_install`).
  - Use options 2017-01-01..2017-12-31 for both reports.
  - For every key in native's `_tb_values`, assert our `init_balance`, `debit`, `credit`, `period_balance` and `end_balance` equal native's within `0.01`.
  - Assert our key set equals native's key set.
- [ ] **Step 2: Run** the test command. Expected: FAIL, because the module or report doesn't exist yet.
- [ ] **Step 3: Implement** the manifest, the report XML and an empty handler subclass with `_name = 'azk.dynamic.trial.balance.report.handler'` and `_inherit = 'account.trial.balance.report.handler'`.
  - Native Initial/End use a single Balance column. To read `init_balance` and `end_balance` from both reports, `_tb_values` reads the `balance` expression where it exists, and debit − credit otherwise.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): report record and native-parity test`.

### Task 2: Classic Debit/Credit split, parents net, total gross

**Files:**
- Modify: `models/trial_balance_handler.py`
- Test: `tests/test_report_engine.py`

**Interfaces:**
- Produces:
  - `_display_single_column_for_initial_and_end_sections(options) -> False`, so Initial/End have debit/credit/balance columns.
  - `_custom_line_postprocessor(report, options, lines)`: call `super()` first, which computes End, then apply the split.
  - Helper `_azk_is_account_level(report, line) -> bool`: true for an `account.account` line without the `parent_account` markup, or for the `undistributed_profits_losses` markup.

- [ ] **Step 1: Write failing tests:**
  - `test_initial_end_classic_split`: for every line and every Initial/End section, assert `debit >= 0`, `credit >= 0`, `debit * credit == 0` and `balance == debit - credit`.
  - `test_reversed_sign_account`: a payable account with a debit balance shows its Initial value in the Debit column.
  - `test_opening_only_account`: an account with only 2016 entries shows Initial = End, and Movement debit = credit = 0.
  - `test_pl_account_across_fiscal_year`: an expense entry on 2016-12-31, with the report on 2017. The expense account's `init_balance == 0`, and `UNDISTRIBUTED.init_balance` includes it, equal to native.
  - `test_last_day_and_day_before`: an entry on `date_to` is in Movement; an entry on `date_from - 1` is in Initial.
  - `test_hierarchy_parent_net_and_total_gross`:
    - Build a parent with two children: child A has a debit balance of 100, child B a credit balance of 30.
    - Parent Initial: Debit 70, Credit 0.
    - TOTAL Initial Debit = the sum of the account-level debits, and TOTAL Initial Credit = the sum of the account-level credits.
    - Unfiltered, TOTAL Initial Debit == TOTAL Initial Credit.
  - `test_multi_company_isolation`: with only company_1 allowed (`allowed_company_ids=[company_1]`), no line carries company_2's accounts or amounts. With both companies allowed, the result equals native under the same context.
  - `test_draft_and_cancelled`:
    - With `all_entries=False`, a draft move is excluded.
    - With `all_entries=True`, it is included.
    - A cancelled move is always excluded.
    - Each case equals native under the same `all_entries`.
- [ ] **Step 2: Run.** Expected: the new tests FAIL.
- [ ] **Step 3: Implement** the split in `_custom_line_postprocessor`.
  - For each line and each column block, read `net` from the Initial and End groups: debit − credit, or `balance` where present.
  - Rewrite the debit, credit and balance columns and their `is_zero`.
  - The TOTAL line's Initial/End debit/credit = the sum over `_azk_is_account_level` lines. Its balance = the net.
  - Parents (`parent_account` markup) are net-split like accounts.
- [ ] **Step 4: Run** the whole `test_report_engine.py`, including the Task 1 parity test. Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): classic debit/credit split`.

### Task 3: Filters — journals, prefixes, analytic, notices

**Files:**
- Modify: `models/trial_balance_handler.py`
- Test: `tests/test_report_filters.py`

**Interfaces:**
- Produces:
  - `options['azk_tb']` dict with keys `journal_ids: list[int]`, `account_prefixes: list[str]`, `analytic_account_ids: list[int]`, `skip_zero_balance: bool`, `account_level: int | False` and `show_amount_currency: bool`. The defaults are empty / False.
  - `_custom_options_initializer(report, options, previous_options)`:
    - Call `super()`.
    - Copy `previous_options['azk_tb']`, sanitized: ints only; prefixes stripped, non-empty, and only `[0-9A-Za-z.]`.
    - Extend `options['forced_domain']`:
      - journals: `('journal_id', 'in', ids)`.
      - prefixes: OR of `('account_id.code', '=like', prefix + '%')`, after escaping `%` and `_`.
    - Analytic: set `options['analytic_groupby_option'] = True` and `options['analytic_accounts_list'] = tuple(ids)`.
  - `_customize_warnings(report, options, all_column_groups_expression_totals, warnings)` adds:
    - a filter-summary warning (template `azk_dynamic_trial_balance.warning_filter_summary`)
    - an unbalanced notice when analytic is set (template `azk_dynamic_trial_balance.warning_analytic_unbalanced`)
  - Before writing the warnings, verify the warnings mechanism in `account_report.py` (`_generate_common_warnings`, how the templates render).

- [ ] **Step 1: Write failing tests** (each one compares with native given the equivalent `forced_domain` where noted):
  - `test_journal_filter_parity`: ours with `azk_tb.journal_ids=[sale]` equals native with `forced_domain=[('journal_id','in',[sale])]`, account by account.
  - `test_multiple_prefixes`: with prefixes `['1', '40']`, every shown account code starts with `1` or `40`. Values equal native with the equivalent forced_domain.
  - `test_prefix_and_undistributed_line`:
    - Prefixes `['1']`: no UNDISTRIBUTED line, and TOTAL equals the sum of the shown accounts.
    - Prefixes containing the unaffected-earnings account code prefix: the UNDISTRIBUTED values equal the unfiltered native UNDISTRIBUTED values.
  - `test_analytic_proportional_share`:
    - A posted expense line of 1000, distributed `{A: 60, B: 40}` (same plan).
    - Filtering on A shows Movement debit 600 on the expense account.
    - Filtering on B shows 400.
  - `test_analytic_unbalanced_notice`: with the analytic filter, warnings contain `warning_analytic_unbalanced`; without it, they don't.
  - `test_prefix_sanitized`: prefix `"1%' OR 1=1"` is dropped, so no injection; the report equals the unfiltered one.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above.
  - For `test_prefix_and_undistributed_line`, the implementer chooses how the UNDISTRIBUTED line is kept or computed without the prefix restriction. One option is to apply prefixes as a domain that keeps `include_initial_balance=False` accounts when the unaffected code matches. The test pins the behaviour.
- [ ] **Step 4: Run** `test_report_filters.py` plus `test_report_engine.py`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): journal, prefix and analytic filters`.

### Task 4: Skip zero balance, hierarchy parents-only level

**Files:**
- Modify: `models/trial_balance_handler.py`
- Test: `tests/test_report_display.py`

**Interfaces:**
- Consumes: `options['azk_tb']` (Task 3).
- Produces: postprocessing in `_custom_line_postprocessor`, run after the Task 2 split.
  - `skip_zero_balance` removes lines whose `init_balance`, period `debit`, period `credit` and `end_balance` are all zero. It then drops parents left with no children.
  - `account_level=N` (requires `options['hierarchy']`) removes lines deeper than `N`. Depth is the count of `parent_account` ancestors + 1. A parent at depth N becomes non-unfoldable.

- [ ] **Step 1: Write failing tests:**
  - `test_skip_zero_keeps_cancelling_movements`: account X has 100 Dr and 100 Cr in the period and no initial. It is shown with skip on. An account with all zeros is hidden.
  - `test_level_rollup_keeps_totals`: on a 3-level tree, for N in 1..3, TOTAL's values are unchanged against full hierarchy, and no line is deeper than N.
  - `test_level_ignored_without_hierarchy`: `account_level=1` with `hierarchy=False` gives a flat list equal to the no-level run.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all test files so far. Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): skip zero balance and hierarchy level`.

### Task 5: Show Amount Currency

**Files:**
- Modify: `data/dynamic_trial_balance_report.xml` (column `amount_currency`; expression `amount_currency`, subformula `amount_currency`), `models/trial_balance_handler.py`
- Test: `tests/test_report_display.py`

**Interfaces:**
- Produces:
  - `_report_engine_trial_balance` override that also selects `SUM(account_move_line.amount_currency) AS amount_currency`.
  - When `azk_tb.show_amount_currency` is True, the line groupby is `account_id,currency_id`, and the account lines are replaced by per-currency lines named `"<code> <name> (<CUR>)"`.
  - The `amount_currency` column is removed from `options['columns']` when the option is off.
  - The column shows the End value, with the line's currency symbol.
- Before implementing, verify how `_get_groupby` / `user_groupby` and `figure_type` with a per-line currency are handled in `account_report.py`. If grouping by `currency_id` as top-level lines is not supported, produce the per-currency lines in the postprocessor from a second grouped engine call. Same test either way.

- [ ] **Step 1: Write failing tests:**
  - `test_amount_currency_lines_sum_to_account`: a receivable has a USD (company) move and an EUR move. With the option on there are two lines, `(USD)` and `(EUR)`. Their company-currency End balances sum to the account's End balance with the option off. The EUR line's amount_currency equals the EUR moves' amount_currency sum.
  - `test_amount_currency_parent_blank`: with hierarchy on and mixed currencies under one parent, the parent's amount_currency cell is empty or None.
  - `test_amount_currency_column_hidden_when_off`: no `amount_currency` column when the option is off.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all test files. Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): amount currency breakdown`.

### Task 6: Wizard, Preview action, menu, security

**Files:**
- Create: `wizard/__init__.py`, `wizard/dynamic_trial_balance_wizard.py`, `wizard/dynamic_trial_balance_wizard_views.xml`
- Modify: `security/ir.model.access.csv`, `__manifest__.py`, `__init__.py`
- Test: `tests/test_wizard.py`

**Interfaces:**
- Produces: model `azk.dynamic.trial.balance.wizard` (TransientModel), with the fields from spec §6 and its help texts verbatim:
  - `date_from`, `date_to`: required. The defaults come from `company.compute_fiscalyear_dates(today)['date_from']` and today.
  - `include_unposted`, `hierarchy_subtotals` (default True), `hierarchy_only_parents`
  - `account_level`: Selection `[('1','1'),…,('5','5')]`
  - `account_prefixes`: Char, comma-separated; the UI uses a tag-like widget if one is available
  - `journal_ids`, `analytic_account_ids`: Many2many
  - `skip_zero_balance`, `show_amount_currency`
  - Also a read-only `posted_entries = True`.
- Methods:
  - `_build_report_options() -> dict`:
    - Calls `report.get_options(previous_options)`.
    - `previous_options` carries `date` (`date_from`, `date_to`, `mode='range'`, `filter='custom'`), `all_entries`, `hierarchy`, `unfold_all=False` and `azk_tb`.
  - `action_preview() -> dict`:
    - Type `ir.actions.client`, tag `account_report`.
    - `context={'report_id': report.id}`.
    - `params={'options': <options>, 'ignore_session': True}`.
  - `action_pdf()` / `action_xlsx()`: in Task 7.
  - Constraints:
    - `_check_dates`: `date_from > date_to` raises ValidationError.
    - `_check_analytic_single_plan`: more than one `root_plan_id` raises ValidationError.
- Security:
  - Access for `account.group_account_readonly` and `account.group_account_basic`: read, write, create, unlink on the wizard.
  - Menu under Accounting › Reporting, visible to the same groups.

- [ ] **Step 1: Write failing tests:**
  - `test_build_options_maps_fields`: the wizard with all fields set produces options whose `date`, `all_entries`, `hierarchy` and `azk_tb` match the fields.
  - `test_options_survive_rerender`: calling `report.get_options(previous_options=options)` again on the result keeps `azk_tb` identical.
  - `test_preview_action`: the action has tag `account_report`, `context.report_id` equals our report and `params.options.azk_tb` is set.
  - `test_dates_validation`: `date_from > date_to` raises `ValidationError`.
  - `test_analytic_single_plan`: accounts from two root plans raise `ValidationError`.
  - `test_access_rights`: a user with only `base.group_user` cannot create the wizard (`AccessError`).
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all tests. Expected: PASS.
- [ ] **Step 5: Manual check.**
  - Start the dev server: the test command without the test flags, plus `--dev=xml`.
  - Open http://localhost:8070 › Accounting › Reporting › Dynamic Trial Balance, then press Preview.
  - Confirm the report opens with the filter-summary warning.
  - Confirm that unfolding a line keeps the filters.
- [ ] **Step 6: Commit** `feat(tb): wizard and preview`.

### Task 7: PDF and XLSX exports

**Files:**
- Modify: `wizard/dynamic_trial_balance_wizard.py`, `models/trial_balance_handler.py` (PDF header / filter summary, if not covered by the warnings)
- Test: `tests/test_exports.py`

**Interfaces:**
- Produces:
  - `action_pdf()` returns `report.export_file(options, 'export_to_pdf')`.
  - `action_xlsx()` returns `report.export_file(options, 'export_to_xlsx')`.
- First, verify in `account_report.py:6747-7100`:
  - which header data the native exporters write (company, dates)
  - that the TB `custom_display_config` PDF templates still apply to our handler
  - Add the filter summary and the analytic notice to both outputs if the exporters don't already include the warnings.

- [ ] **Step 1: Write failing tests:**
  - `test_xlsx_values_match_report`:
    - Call `report.export_to_xlsx(options)` and load `file_content` with openpyxl.
    - The company name and the date range appear in the header rows.
    - For three known accounts, the cells for init/debit/credit/end are **numbers** (not strings) and equal `_tb_values`.
    - The total row is bold.
  - `test_pdf_generates`: `report.export_to_pdf(options)` returns non-empty `file_content` starting with `%PDF`. Needs wkhtmltopdf, present at `thirdparty\wkhtmltopdf.exe`.
  - `test_pdf_header_contains_filters`: the HTML from `_get_pdf_export_html(options, lines)` contains the company name, both dates, and the journal name of an applied journal filter.
  - `test_wizard_export_actions`: `action_pdf` / `action_xlsx` return `type == 'ir_actions_account_report_download'` with the correct `file_generator`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** all tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(tb): pdf and xlsx export`.

### Task 8: Demo data, README, GenAI log, reconciliation table

**Files:**
- Create: `azk_dynamic_trial_balance/demo/demo_data.xml`, `README.md` (repo root, Exercise 2 section), `docs/genai/prompt-log.md`, `azk_dynamic_trial_balance/tests/test_demo_data.py`
- Modify: `__manifest__.py` (`demo` key)

**Interfaces:**
- Demo data (main company, `noupdate="1"`):
  - A parent-account tree 3 levels deep under codes starting `1` and `6`.
  - Two foreign currencies (EUR, GBP) activated, with rates.
  - An analytic plan "Departments" with accounts Sales/Admin, and one 60/40 move.
  - Posted moves in the previous and the current fiscal year; one draft and one cancelled move.
- README Exercise 2 section:
  - features
  - install (`-i azk_dynamic_trial_balance --with-demo`)
  - configuration (none)
  - manual test steps
  - automated tests and how to run them
  - presentation differences from native (§5.2)
  - analytic notice
  - the deviation note (Odoo 20 instead of 18 for Ex3)
  - the per-account reconciliation table
- The reconciliation table is generated by a small script, not by hand: `odoo-bin shell` with `scripts/reconcile_tb.py` prints a markdown table of native vs. ours. Add `scripts/reconcile_tb.py` to the file list.

- [ ] **Step 1: Write failing test** `test_demo_data.test_demo_parity`:
  - Runs only if the demo is loaded; skip when `env.ref(..., raise_if_not_found=False)` is None.
  - Ours vs. native over the current fiscal year: every account's difference is 0.
  - TOTAL Initial Debit == TOTAL Initial Credit.
- [ ] **Step 2: Run** on a fresh DB `azk_tb_demo` with `--with-demo`. Expected: FAIL, because there is no demo yet.
- [ ] **Step 3: Implement** the demo data and `scripts/reconcile_tb.py`.
- [ ] **Step 4: Run** the full suite on `azk_tb_demo` with `--with-demo`, then on `azk_tb_test` without demo. Expected: PASS on both.
- [ ] **Step 5:** Generate the reconciliation table with the script and paste it into the README. Write `docs/genai/prompt-log.md`, a short summary of the prompts and outputs used across this session.
- [ ] **Step 6: Commit** `docs(tb): demo data, README, reconciliation, GenAI log`.
