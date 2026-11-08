# Dynamic Trial Balance — Design

- **Date:** 2026-11-08
- **Module:** `azk_dynamic_trial_balance`
- **Target:** Odoo 20.0 Enterprise (`20.0+e-20261105`), depends on `account_reports`
- **Source requirement:** "Odoo Dev Assessments.pdf", Exercise 2

## 1. Intent

A "Dynamic Trial Balance" report driven by a wizard, with three outputs: on-screen
Preview, PDF and XLSX. Each account line shows Initial, Movement and End sections,
each with Debit, Credit and Balance.

The report is for a technical assessment, so the main goal is **accounting correctness
that can be proven**. A reviewer will compare it with Odoo's native Trial Balance on
the same filters, account by account. They will start with an account that has both
an opening balance and movements, and with an income or expense account across a
fiscal-year boundary. Looks matter least (about 5%). Matching numbers and correct
Opening/Closing logic matter most.

## 2. Goals

1. With equivalent filters, the numbers match the native Odoo 20 Trial Balance
   (`account_reports.trial_balance_report`) **per account**, not only in total.
2. Opening, movement and closing are distinct and correct, including Odoo's
   fiscal-year handling (see §5.1).
3. All wizard options from the spec work: unposted entries, hierarchy with subtotals,
   parents-only hierarchy up to a level (1–5), account prefixes, journals, analytic
   accounts, skip zero balance, show amount currency.
4. Preview, PDF and XLSX show identical lines and numbers, because they come from a
   single source.
5. Automated tests prove parity with the native report and cover the accounting
   edge cases in §8.
6. Multi-company and access rights are respected. No unnecessary `sudo()`, and no raw
   SQL that bypasses Odoo's report query and company rules.

## 3. Non-goals

- Comparison periods or multiple period columns. There is one period: `date_from` to `date_to`.
- Budget columns, cash basis, tax-exigibility variants.
- Editing accounting data from the report.

## 4. Anti-goals (failure even if it "works")

- Good-looking report with numbers that differ from native Odoo.
- Opening balance missing, or computed from all history for P&L accounts.
- Draft entries leaking in when not requested, or cancelled entries ever included.
- Data from companies outside the user's selection/permissions.
- Totals-only comparison that could hide offsetting per-account errors.
- Debit/Credit sign conventions that are inconsistent between sections.

## 5. Decisions made with the user

### 5.1 Architecture: build on the native report engine

The user prefers reusing the Enterprise accounting report engine over rebuilding the
trial balance logic. The module therefore defines its **own `account.report` record**
(a separate report, not modifying the native one). It uses a custom handler that
**inherits** `account.trial.balance.report.handler`. This keeps by construction:

- Initial balance = everything before `date_from`. For accounts with
  `include_initial_balance = False` (income/expense), it counts only from the start of
  the current fiscal year.
- Earlier-year P&L results appear on the native **"Undistributed Profits/Losses"**
  line (`_get_unallocated_earnings_lines`).
- End balance = Initial + Period. It is computed, not queried separately.
- Company scoping via `get_report_company_ids`, and the native access check in
  `_get_report_query`.

The wizard builds the report `options` from its fields and either opens the report
client action (Preview) or renders the same report lines to PDF/XLSX.

Verified in the installed source:
`account_reports/models/account_trial_balance_report.py`,
`account_reports/data/trial_balance.xml`, and `account_reports/models/account_report.py`
(`_get_options_domain`, `_get_report_query`, `_init_options_hierarchy`).

### 5.2 Debit/Credit in Initial and End: classic trial balance

The user chose the classic layout:

| Section  | Debit                          | Credit                            | Balance          |
|----------|--------------------------------|-----------------------------------|------------------|
| Initial  | net initial balance if > 0     | abs(net initial balance) if < 0   | Debit − Credit   |
| Movement | sum of debits in the period    | sum of credits in the period      | Debit − Credit   |
| End      | net end balance if > 0         | abs(net end balance) if < 0       | Initial + Movement |

So in Initial and End, a line has a value in Debit **or** Credit, never both.

**Parent and subtotal lines** (hierarchy, total) work as follows:
- They first sum their children's net **Balance**.
- Then they split that net into Debit or Credit.
- They do not sum the children's Debit and Credit columns.
- Movement Debit/Credit on parents is the plain sum of the children's movement debits
  and credits.

This differs from native Odoo in two ways:
- Native shows a single Balance column for Initial/End.
- When it does show Debit/Credit, native End Debit is cumulative.

Parity is therefore asserted on: Initial Balance, Period Debit, Period Credit,
Period Balance and End Balance. Initial/End Debit/Credit are asserted to be the
correct split of their Balance. The README documents this presentation difference.

### 5.3 Analytic filter: proportional share

When an entry is distributed 60/40 across two analytic accounts and the user filters
on the first, the report shows **only the 60% share**. This matches Odoo's analytic
distribution logic.

Implementation reuses the engine's analytic shadow table. In
`account_reports/models/account_analytic_report.py`, `_get_report_query` swaps
`account_move_line` for rows built from `account.analytic.line` when the
`analytic_groupby_option` key is set. It then filters on `analytic_accounts_list`. The
builder must verify that this works as a filter on the whole report, not only as a
column group.

**Accounts without analytic distribution (decided by the user).** When the analytic filter
is active, only analytic-distributed amounts are reported. Accounts with no analytic
distribution (bank, receivable, payable, tax, …) disappear, so the report is
intentionally **not balanced**. The report shows a visible notice saying so: on screen,
and in the PDF and XLSX headers. This matches Odoo's analytic semantics. The README
documents it.

Known consequence, inherited from Odoo: analytic lines exist only for posted moves.
So with an analytic filter, unposted entries cannot be included. The wizard warns
about this, and the README documents it.

## 6. Wizard (transient model)

| Field | Type | Behaviour / help text |
|---|---|---|
| `date_from`, `date_to` | Date, required | Not in the spec, but needed for any trial balance and for the PDF header. Default: start of the current fiscal year to today. Constraint: `date_from <= date_to`. |
| Posted entries | always on | Displayed as a read-only, checked option. |
| `include_unposted` | Boolean | Draft entries are included; cancelled entries never are. Same as native `all_entries`. |
| `hierarchy_subtotals` | Boolean | Show the parent-account tree with subtotals, as native. |
| `hierarchy_only_parents` | Boolean | When on, shows `account_level` (selection 1–5). |
| `account_level` | Selection 1–5 | Level 1 = accounts without a parent; level N = down to depth N. Deeper accounts roll up into their nearest shown ancestor, so totals never change. |
| `account_prefixes` | multi-text (tags) | Help: "Specify the account prefix to view only matching accounts. If no prefix is entered, all accounts will be displayed." Matches accounts whose code **starts with** any prefix. |
| `journal_ids` | Many2many `account.journal` | The spec says Many2One, but "select specific journals" means several, so this is Many2many. Help: "Select specific journals to include in the report, or leave the field empty to include all journals." |
| `analytic_account_ids` | Many2many `account.analytic.account` | Same reasoning. Help: "Select specific analytic accounts to include in the report, or leave the field empty to include all." |
| `skip_zero_balance` | Boolean | Help from the spec. Hides an account only when its Initial, Movement Debit, Movement Credit and End are **all** zero. An account whose movements cancel out (100 Dr / 100 Cr) is kept. |
| `show_amount_currency` | Boolean | Help from the spec. See §7. |
| Buttons | Preview / PDF / XLSX | |

Hierarchy in Odoo 20 is based on `account.account.parent_id`; `account.group` no longer
exists (verified). "Group Account" in the spec means parent accounts.

Company: the companies currently selected in the user's company switcher, the same as
the native report.

## 7. Show Amount Currency

- Each account is split into one line per transaction currency (`currency_id`).
- Each line adds an **Amount Currency** column: the sum of `amount_currency`, formatted
  with that currency's symbol.
- Its Debit/Credit/Balance are in company currency, for that currency's journal
  items only.
- Parent/subtotal lines show **no** Amount Currency, because summing different
  currencies has no meaning. They show company-currency figures only.
- The per-currency lines of an account add up to the account's figures without the
  option.

## 8. Testing

TDD, with Odoo `TransactionCase` / `AccountTestInvoicingCommon`, run through
`odoo-bin --test-enable` on a dedicated new database. Existing databases (`noktest`,
`nokasse`, `odoo20_dev`) are never touched.

**Parity tests** compare our output with `account_reports.trial_balance_report`. They
use the same dates, companies and draft option, and compare **per account**.

**Edge cases:**
- Period with no movements.
- Account with only an opening balance.
- Entry dated on the last day of the period, and on the day before `date_from`.
- Account with a reversed (unusual-sign) balance.
- Income/expense account across a fiscal-year boundary: the earlier year must go to
  Undistributed Profits/Losses, not to the account's initial balance.
- Draft included or excluded; cancelled never included.
- Multi-company: data from another company never appears.
- Journal filter.
- Prefix filter with several prefixes.
- Analytic 60/40 distribution shows exactly the share.
- Skip zero balance, with the cancelling-movements account kept.
- Hierarchy levels 1–5 keep the grand total unchanged.
- Amount currency per-currency lines add up to the account total.
- Wizard validation: `date_from > date_to` is rejected.

**Export tests:** the XLSX is generated and read back with `openpyxl`, if available,
or checked structurally. The PDF action is generated without error.

The README includes manual test steps and a per-account reconciliation table
(native vs. ours, difference = 0) taken from the demo data.

## 9. Demo data

Loaded as module demo data:
- A parent-account tree 3–4 levels deep.
- Posted, draft and cancelled entries.
- Two foreign currencies.
- An analytic plan with accounts and a 60/40 distribution.
- Entries across two fiscal years.

## 10. Outputs

- **Preview:** the report client action with the wizard's options applied. It keeps
  the standard dynamic-report look, search and unfold.
  - **Filter editing (decided by the user).** The native filters stay editable in
    the report's filter bar: dates, unposted entries, hierarchy, search bar, unfold
    and companies.
  - The wizard-only options (journals, prefixes, analytic accounts, level,
    skip-zero, amount currency) appear as a **read-only summary** in the report
    header.
  - To change them, the user re-opens the wizard. No custom OWL filter components
    are built.
  - The wizard-only options must survive report re-renders, through
    `previous_options`.
- **PDF:** a header with company name, date range and active filters, then the
  table. Hierarchy is shown by indentation, and totals are bold.
- **XLSX:** values written as numbers with a number format (not text), hierarchy shown
  by indentation, totals bold, and a header with company, range and filters.

## 11. Builder's calls (settled after the builder check)

- **Analytic accounts from several plans.** In Odoo each plan distributes 100% of a line
  on its own, so mixing plans would double count. The wizard therefore requires the
  selected analytic accounts to belong to **one root plan**, and raises a validation
  error otherwise.
- **Amount Currency column.** One column: the account's **End** balance in that
  currency, as of `date_to`. With the option on, an account is shown as one line per
  currency, labelled `code name (CUR)`. These lines replace the account line. Parents
  and totals still sum them in company currency. Skip-zero and level roll-up apply to
  each currency line.
- **Parity under filters.** Parity tests run the native report with the same filter
  injected through `forced_domain`. This applies to journals, account prefixes and
  analytic accounts. Level roll-up is checked by an invariant instead: totals are
  unchanged against the full hierarchy.
- **Undistributed Profits/Losses under filters.** It follows the journal, analytic and
  draft filters, because it is computed from the same filtered journal items. With an
  account-prefix filter, it is shown only when a prefix matches the code of the
  company's `equity_unaffected` account, since conceptually it belongs to that account.

- **Grand total line (planning-time correction).** Parent lines are net-split (§5.2).
  The grand total, however, **sums the account-level lines' split Debit and Credit
  columns**. Account-level lines are the leaf accounts plus Undistributed
  Profits/Losses.
  - So Total Initial Debit = the sum of all debit balances, and Total Initial
    Credit = the sum of all credit balances. In an unfiltered report the two are equal.
  - Total Balance stays the net.
  - Net-splitting the total would always show 0 / 0, which defeats the purpose of a
    trial balance.

## 12. Left to the builder

- Exact way to inject the extra filters into the inherited handler or report options.
  Options include `forced_domain`, overriding `_get_options_domain` / `_custom_options_initializer`,
  or a groupby on `currency_id` for amount currency.
- Whether PDF/XLSX reuse `account.report` export hooks or a dedicated QWeb/xlsxwriter renderer.
  Either way, they must consume the same computed lines.
- Exact demo-data volumes and the README reconciliation table format.
- Security: an `ir.model.access` row for the wizard, limited to accounting groups that can read
  the native report.
