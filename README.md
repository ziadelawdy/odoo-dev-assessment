# Odoo Developer Technical Assessment

Submission by **Ziad Elawdy** for the Odoo Developer technical assessment.
Two of the three exercises were selected:

| Exercise | Module(s) | Status |
|---|---|---|
| 2 — Dynamic Trial Balance | [`azk_dynamic_trial_balance`](azk_dynamic_trial_balance) | **Done** — see below |
| 3 — POS Enhancements | [`azk_pos_salesperson`](azk_pos_salesperson), [`azk_pos_enhanced_receipt`](azk_pos_enhanced_receipt) | **Done** — see below |
| 1 — Odoo Partner Monitor | — | Not selected |

**Target version: Odoo 20.0 Enterprise** (`20.0+e-20261105`). The assessment text mentions Odoo 18
for Exercise 3. The modules target the Odoo 20 instance used for development and testing,
and every framework API was checked against the installed Odoo 20 source.

Design notes, plans and the GenAI prompt log are in [`docs/`](docs).

---

## Exercise 2 — Dynamic Trial Balance (`azk_dynamic_trial_balance`)

### What it does

A wizard (*Accounting › Reporting › Statement Reports › Dynamic Trial Balance*) produces a
trial balance with **Initial Balance**, **Movement** and **End Balance** sections. Each section
has **Debit, Credit and Balance** columns. There are three outputs:

- **Preview**: the standard Odoo dynamic report UI, with search, unfold, audit of a cell,
  and the date / draft / hierarchy / company filters.
- **PDF**: company, period and every applied filter appear in the header.
- **XLSX**: a header with company, period and filters. Numeric cells, hierarchy
  indentation and a bold total.

| Wizard field | Behaviour |
|---|---|
| Start / End Date | Period of the report. Default: current fiscal year start to today. |
| Posted Entries | Always included (read-only). |
| Include Unposted Entries | Adds draft entries. Cancelled entries are never included. |
| Hierarchy and Subtotals | Parent-account tree with subtotals. Odoo 20 builds the account hierarchy on `account.account.parent_id`; `account.group` no longer exists. |
| Hierarchy Only Parents + Account Level Up To (1–5) | Keeps the tree down to the chosen depth. Deeper accounts are rolled into their nearest shown parent, so totals are unchanged. |
| Accounts | One or more account-code prefixes, comma-separated (e.g. `1, 40`). Letters, digits, `.` and `-` (the characters Odoo allows in codes). Anything else is rejected. Empty = all accounts. |
| Journals | Several journals. Empty = all. They are passed to the native Journals filter of the report. |
| Analytic Accounts | Several analytic accounts **of one plan**. Empty = all. Visible when *Analytic Accounting* is enabled (Accounting › Settings). |
| Skip Zero Balance | Hides accounts with zero initial balance, zero movements and zero end balance. An account whose movements cancel out (100 Dr / 100 Cr) is kept. |
| Show Amount Currency | Splits each account into one line per transaction currency, with an *Amount Currency* column (end balance in that currency, with its symbol). |

### Design

The module defines its **own `account.report`**. Its custom handler **inherits the native
Trial Balance handler** (`account.trial.balance.report.handler`). The goal was numbers that
match Odoo's Trial Balance by construction, not by re-implementation:

- **Initial balance** = everything before the start date.
- For income/expense accounts (`include_initial_balance = False`), the initial balance only
  counts from the start of the current fiscal year.
- Earlier-year P&L results go to Odoo's **Undistributed Profits/Losses** line.
- **End balance** = Initial + Movement.
- **Company scoping** and the accountant access check come from the native report query.
  There is no `sudo()` and no raw SQL outside the engine's own query builder.

On top of the engine:

1. **Classic trial balance presentation.** Native Odoo shows Initial and End as a single net
   *Balance* column. Here, a net debit balance goes to *Debit*, a net credit balance to *Credit*,
   and *Balance = Debit − Credit*. Parent accounts are split on their net balance. The **grand
   total sums the accounts' Debit and Credit columns**, so total debit balances = total credit
   balances is visible. Netting the total would always show 0 / 0.
2. **Wizard-only filters** travel in the report options under `azk_tb` and survive every
   re-render of the Preview. Journals and account prefixes become a `forced_domain`.
   - Prefixes are validated so they cannot inject `=like` wildcards.
   - With a prefix filter, *Undistributed Profits/Losses* is shown only when a prefix
     matches the company's unaffected-earnings account. It is then computed without the
     prefix restriction, because it aggregates P&L accounts.
3. **Analytic filter = proportional share.** An entry split 60/40 between two analytic accounts
   shows 60 % under the first. This reuses the engine's analytic shadow table, the same logic
   as Odoo's analytic group-by.
   - Accounts without analytic distribution (bank, receivable, payable, taxes…) are not
     part of an analytic view, so **a filtered report is intentionally not balanced**. A
     visible notice says so on screen, in the PDF and in the XLSX.
   - Analytic lines only exist for posted entries.
4. **One line per account and company.** With several companies selected, Odoo's default *consolidation* regroups the trial balance by account code (accounts become hidden sub-lines). This report turns consolidation off, because every feature here (prefixes, hierarchy, currencies, skip-zero) works on real account lines. The numbers equal the native report with consolidation off.
5. **Filters editable in the report.** The report has its own filter bar (a custom
   `AccountReportFilters` component, the same mechanism native reports use). It contains:
   - an *Accounts* prefix field;
   - switches for *Unposted Entries*, *Hierarchy and Subtotals*, *Only Parents* (with a level
     selector from 1 to 5), *Skip Zero Balance* and *Amount Currency*;
   - Odoo's native *Journals* dropdown and date filter;
   - **PDF** and **XLSX** buttons.

   Every change reloads the report immediately and survives a refresh. Only the analytic
   accounts are chosen in the wizard; they appear in the summary banner. The report can also
   be opened directly from the client action `action_azk_dynamic_trial_balance_report`.

### Installation

1. Put this repository on the Odoo `addons_path`.
2. Update the Apps list.
3. Install **Dynamic Trial Balance**. It depends on `account_reports` (Odoo Enterprise).

```bash
python odoo-bin -c <your.conf> -d <db> -i azk_dynamic_trial_balance --with-demo
```

No configuration is needed. Access is limited to the accounting groups that can read the
native reports (`account.group_account_readonly`, `account.group_account_basic`).

### Demo data

Installing with demo data (`--with-demo`) runs a loader. It is written in Python so that
account codes, journals and fiscal-year dates fit any database, and it is idempotent. It creates:

- a 3-level account tree (`1000 › 1100 › 1110/1120`, `6000 › 6100/6200`, …);
- two foreign currencies with rates;
- an analytic plan with two departments and a 60/40 salary entry;
- posted entries over the previous and the current fiscal year;
- one draft and one cancelled entry.

### Testing strategy

**Automated tests**: 51 tests in `azk_dynamic_trial_balance/tests`, all passing on Odoo 20.
They were written test-first (each one was seen failing before the code existed).

| File | Covers |
|---|---|
| `test_report_engine.py` | Default options with several companies and *totals below sections* (regression found in the Preview). Parity with native Odoo per account. Classic split. Reversed-sign account. Opening-only account. P&L across fiscal years (Undistributed P/L). Last day of period / day before. Parents net-split and grand total. Multi-company isolation. Draft included/excluded, cancelled never. |
| `test_report_filters.py` | Journal and multi-prefix filters (parity with native under the same domain). Prefix + Undistributed P/L rule. Analytic 60/40 share. Unbalanced notice. Prefix injection attempt (`1%' OR 1=1`). |
| `test_report_display.py` | Skip-zero (keeps cancelling movements, drops empty parents). Hierarchy levels 1–3 keep totals. Amount-currency lines add up to the account and show their currency symbol. Parents never sum mixed currencies. Column hidden when off. |
| `test_wizard.py` | Field-to-options mapping. Options survive re-render. Preview action. Date validation. Single-plan analytic validation. Access rights. |
| `test_exports.py` | XLSX header (company, period, filters), numeric values equal to the report, bold total, analytic notice. PDF header filters. PDF export path (the wkhtmltopdf call is stubbed: inside a test transaction it would fetch its CSS from the same blocked server). Wizard export actions. A real PDF and XLSX were also generated from the demo database with the server running. |
| `test_review_fixes.py` | Regressions from the independent code review: unfolded accounts (partner / journal-item sub-lines) never inflate the total, with and without Amount Currency. Expanding one account never adds Undistributed P/L lines. Prefixes with `-`. The wizard rejects invalid prefixes. Comparison periods are not offered. |
| `test_report_filter_bar.py` | Filter bar component registered. PDF/XLSX buttons in the bar. Native journal filter, also fed by the wizard. **Tour:** every switch, the prefix field and the level selector update the report. |
| `test_demo_data.py` | Demo loader content and idempotency. Per-account parity with native over the demo data, with and without hierarchy. Total debit = total credit. |

Run them:

```bash
python odoo-bin -c <your.conf> -d <test_db> -i azk_dynamic_trial_balance --test-tags /azk_dynamic_trial_balance --stop-after-init
```

The **parity tests** are the core of the strategy. Odoo's own Trial Balance is the reference
dataset, and every account's initial, debit, credit and end values must be equal. Totals alone
are not enough, because offsetting errors would hide.

**Manual test steps** (on a database installed with `--with-demo`):

1. Open *Accounting › Reporting › Statement Reports › Dynamic Trial Balance*. Keep the default
   dates and press **Preview**.
   - Expected: the demo tree is shown with Initial / Movement / End × Debit / Credit / Balance.
   - Expected: the total line has equal Debit and Credit in Initial and End.
2. Open the native *Trial Balance* for the same period. Compare `1110 Main Bank (Demo)` and
   `6100 Salaries (Demo)`. Expected: the same initial, movement and end balances.
3. Wizard › *Accounts* `11` › Preview. Expected: only `11xx` accounts, and the filter banner
   is shown.
4. Wizard › *Analytic Accounts* `Sales Dept (Demo)` › Preview. Expected: Salaries movement
   **4,800** (60 % of 8,000), and the "not balanced" notice.
5. Wizard › *Hierarchy Only Parents*, level **1** › Preview. Expected: only the top accounts,
   with the same total as step 1.
6. Wizard › *Show Amount Currency* › Preview. Expected: `1200 Customers (Demo)` split into a
   company-currency line and a foreign-currency line, the latter showing its amount in that
   currency.
7. Wizard › **PDF** and **XLSX**. Expected: the same lines and numbers as the Preview, with
   company, period and filters in the header.

### Reconciliation with the native Trial Balance (demo data)

Generated by [`scripts/reconcile_tb.py`](azk_dynamic_trial_balance/scripts/reconcile_tb.py), not typed by hand:

Company: YourCompany — period 2026-01-01 .. 2026-12-31
| Account | Native Initial | Ours Initial | Native Debit | Ours Debit | Native Credit | Ours Credit | Native End | Ours End | Difference |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Main Bank (Demo) | 47,000.00 | 47,000.00 | 0.00 | 0.00 | 8,500.00 | 8,500.00 | 38,500.00 | 38,500.00 | 0.00 |
| Petty Cash (Demo) | 0.00 | 0.00 | 500.00 | 500.00 | 0.00 | 0.00 | 500.00 | 500.00 | 0.00 |
| Customers (Demo) | 12,000.00 | 12,000.00 | 1,100.00 | 1,100.00 | 0.00 | 0.00 | 13,100.00 | 13,100.00 | 0.00 |
| Bank | 0.00 | 0.00 | 7,363.20 | 7,363.20 | 2,322.27 | 2,322.27 | 5,040.93 | 5,040.93 | 0.00 |
| Bank Suspense Account | 0.00 | 0.00 | 2,322.27 | 2,322.27 | 4,863.20 | 4,863.20 | -2,540.93 | -2,540.93 | 0.00 |
| Accounts Receivable | 0.00 | 0.00 | 151,499.00 | 151,499.00 | 97,662.50 | 97,662.50 | 53,836.50 | 53,836.50 | 0.00 |
| Tax Paid | 0.00 | 0.00 | 4.50 | 4.50 | 4.50 | 4.50 | 0.00 | 0.00 | 0.00 |
| Accounts Payable | 0.00 | 0.00 | 34.50 | 34.50 | 656.77 | 656.77 | -622.27 | -622.27 | 0.00 |
| Tax Received | 0.00 | 0.00 | 12,412.50 | 12,412.50 | 18,675.00 | 18,675.00 | -6,262.50 | -6,262.50 | 0.00 |
| Share Capital (Demo) | -50,000.00 | -50,000.00 | 0.00 | 0.00 | 0.00 | 0.00 | -50,000.00 | -50,000.00 | 0.00 |
| Product Sales (Demo) | 0.00 | 0.00 | 0.00 | 0.00 | 1,100.00 | 1,100.00 | -1,100.00 | -1,100.00 | 0.00 |
| Product Sales | 0.00 | 0.00 | 82,750.00 | 82,750.00 | 132,824.00 | 132,824.00 | -50,074.00 | -50,074.00 | 0.00 |
| Salaries (Demo) | 0.00 | 0.00 | 8,000.00 | 8,000.00 | 0.00 | 0.00 | 8,000.00 | 8,000.00 | 0.00 |
| Expenses | 0.00 | 0.00 | 652.27 | 652.27 | 30.00 | 30.00 | 622.27 | 622.27 | 0.00 |
| Result Brought Forward | -9,000.00 | -9,000.00 | 0.00 | 0.00 | 0.00 | 0.00 | -9,000.00 | -9,000.00 | 0.00 |
| Total | 0.00 | 0.00 | 266,638.24 | 266,638.24 | 266,638.24 | 266,638.24 | 0.00 | 0.00 | 0.00 |
Lines only in ours: none — largest difference: 0.00

Re-run it with:

```bash
python odoo-bin shell -c <your.conf> -d <db> --no-http < azk_dynamic_trial_balance/scripts/reconcile_tb.py
```

### Known limitations

- Single period by design: the native *Comparison* filter is not offered.
- With *Unfold All*, the native report omits its *Cumulative Translation Adjustment* line (multi-currency companies). This report inherits that behaviour.

- With an analytic filter, the *Amount Currency* column shows the journal item's full foreign
  amount (the analytic shadow table carries `amount_currency` unprorated).
- The trial-balance engine method is re-declared in the handler to add an `amount_currency`
  aggregate (the native SELECT is built inline). Its logic is otherwise identical, and the
  parity tests guard it.
- With *Show Amount Currency*, Debit/Credit splits are per currency line, so total Debit/Credit
  can differ from the option-off report. Net balances are identical.

---

## Exercise 3 — POS Enhancements (`azk_pos_salesperson`, `azk_pos_enhanced_receipt`)

The exercise is split into two independent modules, as required. Each module installs on its
own. Installed together, they compose with no bridge module (see *Conflicts* below).

### Salesperson Assignment (`azk_pos_salesperson`)

- **Salespersons** (*Point of Sale › Configuration › Salespersons*): name (required), phone, and
  an optional related employee. They are archivable and per company.
- **Per POS settings**, on the POS form and on the POS Settings page:
  - *Salesperson Assignment* (`active_salesperson_feature`);
  - *Allowed Salespersons* (`allowed_sale_person_ids`).
- **Offline:** the allowed salespersons are loaded with the POS data, and assignments are stored
  on the order and synced with it. Nothing calls the server.
- **In the POS (feature on):**
  - a person icon on every order line assigns a salesperson to **that line only**;
  - **Assign Salesperson to Order** assigns a salesperson to **every line**, and also becomes the
    order salesperson. **Lines added afterwards inherit it.** A line changed individually keeps
    its value.
  - Pressing *Assign to Order* again overwrites all lines (assessment test case 3).
  - The popup is the native selection popup. It lists the allowed salespersons plus
    **No salesperson**, which clears the value.
  - A product added again only merges into a line credited to the same salesperson, so two
    salespersons selling the same product keep separate lines.
  - Combo children follow their parent.
- **Backend:** `salesperson_id` is shown in both order-line list views (*All sales lines* and
  *Sale line*), and on the order form (order salesperson and line column).
- **Receipt:** `Salesperson: <name>` is printed under the product, only when the feature is on
  and the line is assigned. This works on the client receipt and on the server receipt
  (email/download).

### Enhanced Receipt Layout (`azk_pos_enhanced_receipt`)

- **Per POS settings:**
  - *Customized Receipt* (`use_customized_receipt`);
  - *Receipt Logo* (`receipt_logo`);
  - *Receipt Company Name* / *Details* (`company_name`, `company_details`);
  - *Show Customer Details* (`show_customer_details`).
- **Enhanced layout**, from top to bottom:
  1. Receipt logo, falling back to the standard logo when none is uploaded.
  2. Company name and details.
  3. Customer name and address, when enabled.
  4. Ticket and date.
  5. A **table** with Product | Qty | Price | Total. The gift/basic receipt has Product | Qty
     only.
  6. Totals, taxes, payments and footer, as native.

  The native customer block and the footer company block are replaced, not duplicated.
- **Option off:** the native receipt, unchanged.
- **Security:** company name and details are `Html` fields with Odoo's sanitizer, instead of the
  spec's *Text*, because the spec allows HTML. Scripts and event handlers are stripped on save,
  so nothing executable reaches the receipt.

### Installation and configuration

```bash
python odoo-bin -c <your.conf> -d <db> -i azk_pos_salesperson,azk_pos_enhanced_receipt --with-demo
```

Demo data creates *Salesperson A, B, C*. To set up the assessment configurations (§4.1), go to
*Point of Sale › Configuration › Point of Sale* and create or open four POS:

| POS | Salesperson Assignment | Allowed | Customized Receipt | Receipt fields |
|---|---|---|---|---|
| `POS_Sales_Enabled_Enhanced_Receipt` | ✓ | A, B | ✓ | logo, company name/details, customer details ✓ |
| `POS_Sales_Enabled_Default_Receipt` | ✓ | A, B | ✗ | — |
| `POS_Sales_Disabled_Enhanced_Receipt` | ✗ | — | ✓ | logo, company name/details, customer details ✓ |
| `POS_All_Disabled` | ✗ | (may be set, ignored) | ✗ | (may be set, ignored) |

### Manual test steps (assessment §4.2)

1. **Visibility.** Open a session on each POS and sell something.
   - The line icon and the *Assign Salesperson to Order* button appear only when Salesperson
     Assignment is on.
   - The receipt shows the branded table layout only when Customized Receipt is on.
2. **Per line.** Add *X* and *Y*. Click the person icon on X and pick A; on Y pick B. Pay.
   - The receipt shows A under X and B under Y.
   - *Point of Sale › Orders › Order lines* shows the same.
3. **Global overwrites.** Assign A and B per line, then *Assign Salesperson to Order* → C. Both
   lines show C on screen, on the receipt and in the backend.
4. **No assignment.** No name anywhere, and an empty column in the backend.
5. **Change during a session.** Enable both features on an open session's POS in the backend
   and sell without reloading. The UI and receipt are unchanged until the POS is reloaded
   (expected POS behaviour).

### Automated tests

45 tests, all passing on Odoo 20 with both modules installed. They were written test-first.
The POS tours drive Chrome through real sales.

| Module / file | Covers |
|---|---|
| `azk_pos_salesperson/tests/test_salesperson_backend.py` | Required name. Loads only the allowed salespersons, and none when the feature is off. Order sync stores the line and order salesperson. Access rights (POS user read, manager write). Backend views. |
| `azk_pos_salesperson/tests/test_salesperson_receipt.py` | Receipt data and server-rendered receipt: name under the product; hidden when the feature is off or the line is unassigned. |
| `azk_pos_salesperson/tests/test_salesperson_ui.py` | **Tours.** Test cases 2, 3 and 4. New lines inherit the order salesperson. Merge rule. Combo children. Assignments survive a browser refresh. UI hidden when the feature is off. |
| `azk_pos_enhanced_receipt/tests/test_enhanced_backend.py` | Fields. HTML sanitizing (`<script>`, `onerror`). Form and settings views. Settings write-through. No name clash with native fields. |
| `azk_pos_enhanced_receipt/tests/test_enhanced_receipt.py` | Enhanced layout, native when off, customer hidden, logo fallback, basic receipt table, no duplicated company info or unit price. |
| `azk_pos_salesperson/tests/test_review_fixes.py` | Regressions from the independent review. Editing a combo keeps its children credited. POS refunds keep the salesperson. The order button is available on small screens (phone/tablet viewport tour). Multi-company checks. Employee records are never loaded into the POS. |
| `azk_pos_enhanced_receipt/tests/test_both_modules.py` | Salesperson printed once, inside the enhanced table. **Tours:** test case 1 on the four configurations by name, and test case 5, each checking the **client-rendered** receipt. |

```bash
python odoo-bin -c <your.conf> -d <test_db> -i azk_pos_salesperson,azk_pos_enhanced_receipt --test-tags /azk_pos_salesperson,/azk_pos_enhanced_receipt --stop-after-init
```

The POS tours need Chrome and the Python package `websocket-client`. Without it, Odoo *skips*
the tours.

### Conflicts when both modules are installed (assessment question)

Both modules extend the **same receipt** and the **same POS settings**. These are the conflicts
that could happen, and how this design avoids them:

1. **The same QWeb receipt templates are extended twice.**
   - The salesperson module only appends inside the native `extra-info` hook of
     `pos_orderline_receipt_information`.
   - The enhanced receipt replaces the line loop with a table, but its Product cell **re-uses**
     `pos_orderline_receipt_information`.
   - So the salesperson name appears inside the table with no dependency between the modules.
     `test_both_modules.py` verifies it.
   - The rule that avoids this class of conflict: target stable `name`d hooks, and never
     replace a template another addon extends.
2. **Both patch the receipt data generator** (JS `GeneratePrinterData` and its Python mirror).
   Each patch calls `super()` and only adds its own keys (`azk_salesperson`, `azk_enhanced`, …).
3. **Both add settings to the same views.** Each uses its own `<setting id>`, positioned
   relative to native anchors.
4. **Field name clashes.** The new `pos.config` fields do not exist natively (tested). Native
   `custom_logo`/`logo` are left untouched.
5. **Load order.** Neither module depends on the other. If two addons ever needed to cooperate
   more tightly, the standard resolution is a small **bridge module** (`auto_install: True`,
   depending on both) that holds the glue code. This design does not need one.

### Notes and decisions

- **Odoo 20:**
  - The POS receipt is server QWeb rendered on the client; the spec's `XmlReceipt` no longer
    exists, so the extensions target `pos_order_receipt*`.
  - Security uses the Odoo 20 `ir.access` format.
  - Binary fields are `BinaryBytes`.
- **Design calls:**
  - the order-level salesperson, so inheritance survives reloads and offline restarts;
  - the "No salesperson" entry;
  - the merge rule;
  - `Html` instead of `Text`;
  - settings on both the POS form and the Settings page;
  - archived salespersons stay on past orders.
