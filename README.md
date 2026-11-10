# Odoo Developer Technical Assessment

**Candidate:** Ziad Elawdy · **Target:** Odoo 20.0 Enterprise (`20.0+e-20261105`)

Three Odoo modules for Exercises 2 and 3 of the assessment. They were designed from written
specifications, built test-first, and checked against the installed Odoo 20 source.

| Exercise | Module | Status | Automated tests |
|---|---|---|---:|
| 2 — Dynamic Trial Balance | [`azk_dynamic_trial_balance`](azk_dynamic_trial_balance) | ✅ Complete | 51 |
| 3 — POS Salesperson Assignment | [`azk_pos_salesperson`](azk_pos_salesperson) | ✅ Complete | 77 (Exercise 3, both modules together) |
| 3 — POS Enhanced Receipt Layout | [`azk_pos_enhanced_receipt`](azk_pos_enhanced_receipt) | ✅ Complete | |
| 1 — Odoo Partner Monitor | — | Not selected (two of three required) | — |

All tests pass on Odoo 20.0 Enterprise.

## Contents

1. [Quick start](#1-quick-start)
2. [Repository layout](#2-repository-layout)
3. [Exercise 2 — Dynamic Trial Balance](#3-exercise-2--dynamic-trial-balance)
4. [Exercise 3 — POS Enhancements](#4-exercise-3--pos-enhancements)
5. [Assumptions and deviations](#5-assumptions-and-deviations)
6. [Engineering process and GenAI usage](#6-engineering-process-and-genai-usage)

---

## 1. Quick start

**Requirements**
- Odoo 20.0 **Enterprise**. The Trial Balance depends on `account_reports`.
- For the POS browser tours: Chrome and the Python package `websocket-client`. Without
  them, Odoo skips the tours.

**Install** (add this repository to `addons_path` first):

```bash
python odoo-bin -c <your.conf> -d <db> -i azk_dynamic_trial_balance,azk_pos_salesperson,azk_pos_enhanced_receipt --with-demo
```

**Run the automated tests:**

```bash
python odoo-bin -c <your.conf> -d <test_db> -i azk_dynamic_trial_balance --test-tags /azk_dynamic_trial_balance --stop-after-init
```

```bash
python odoo-bin -c <your.conf> -d <test_db> -i azk_pos_salesperson,azk_pos_enhanced_receipt --test-tags /azk_pos_salesperson,/azk_pos_enhanced_receipt --stop-after-init
```

Each module installs on its own. The two POS modules also work together with no bridge
module (see [Conflicts](#45-conflicts-when-both-pos-modules-are-installed)).

## 2. Repository layout

```text
azk_dynamic_trial_balance/   Exercise 2: wizard, report handler, PDF/XLSX, demo loader, tests
  scripts/reconcile_tb.py    Account-by-account reconciliation with the native Trial Balance
azk_pos_salesperson/         Exercise 3: salesperson model, POS UI, receipt line, reports
azk_pos_enhanced_receipt/    Exercise 3: configurable receipt layout, checkout options
docs/
  genai/prompts.md           Prompts that directed the work, skills used, token usage
  genai/prompt-log.md        What the AI produced for each prompt
  superpowers/specs/         Design document for each feature
  superpowers/plans/         Test-first implementation plan for each feature
```

---

## 3. Exercise 2 — Dynamic Trial Balance

### 3.1 Features

A wizard (*Accounting › Reporting › Statement Reports › Dynamic Trial Balance*) produces a
trial balance with **Initial Balance**, **Movement** and **End Balance** sections. Each
section has **Debit, Credit and Balance** columns. There are three outputs:

- **Preview**: the standard Odoo dynamic report UI, with search, unfold, audit of a cell,
  and an editable filter bar.
- **PDF**: company, period and every applied filter appear in the header.
- **XLSX**: a header with company, period and filters. Numeric cells, hierarchy
  indentation and a bold total.

| Wizard field | Behaviour |
|---|---|
| Start / End Date | Period of the report. Default: start of the current fiscal year to today. |
| Posted Entries | Always included (read-only). |
| Include Unposted Entries | Adds draft entries. Cancelled entries are never included. |
| Hierarchy and Subtotals | Parent-account tree with subtotals, built on `account.account.parent_id`. `account.group` no longer exists in Odoo 20. |
| Hierarchy Only Parents + Account Level Up To (1–5) | Keeps the tree down to the chosen depth. Deeper accounts roll into their nearest shown parent, so totals are unchanged. |
| Accounts | One or more account-code prefixes, comma-separated (e.g. `1, 40`). Allowed characters: letters, digits, `.` and `-`, the characters Odoo allows in codes. Anything else is rejected. Empty = all accounts. |
| Journals | Several journals. Empty = all. Passed to the report's native Journals filter. |
| Analytic Accounts | Several analytic accounts **of one plan**. Empty = all. Visible when *Analytic Accounting* is enabled. |
| Skip Zero Balance | Hides accounts with zero initial balance, zero movement and zero end balance. An account whose movements cancel out (100 Dr / 100 Cr) is kept. |
| Show Amount Currency | Splits each account into one line per transaction currency, with an *Amount Currency* column: the end balance in that currency, with its symbol. |

**Filter bar.** The Preview has its own filter bar (a custom `AccountReportFilters`
component, the same mechanism native reports use). It holds:
- the *Accounts* prefix field;
- switches for *Unposted Entries*, *Hierarchy and Subtotals*, *Only Parents* (with a level
  selector), *Skip Zero Balance* and *Amount Currency*;
- the native *Journals* and date filters;
- **PDF** and **XLSX** buttons.

Every change reloads the report at once and survives a page refresh. The report can also be
opened directly from the client action `action_azk_dynamic_trial_balance_report`.

### 3.2 Configuration

None is required. Access follows the accounting groups that can read the native reports
(`account.group_account_readonly`, `account.group_account_basic`).

### 3.3 Architecture

The module defines its **own `account.report`**. Its handler **inherits the native Trial
Balance handler** (`account.trial.balance.report.handler`). The numbers therefore match
Odoo's Trial Balance by construction, not by re-implementation.

- **Initial balance** is everything before the start date. For income and expense accounts
  (`include_initial_balance = False`), it counts only from the start of the current fiscal
  year. Earlier-year results go to Odoo's **Undistributed Profits/Losses** line.
- **End balance** = Initial + Movement.
- **Security.** Company scoping and the accountant access check come from the native report
  query. There is no `sudo()` and no raw SQL outside the engine's own query builder.

Design decisions on top of the engine:

1. **Classic presentation.** Native Odoo shows Initial and End as one net *Balance* column.
   Here a net debit goes to *Debit*, a net credit goes to *Credit*, and *Balance = Debit −
   Credit*. Parent accounts are split on their net balance. The **grand total sums the
   accounts' Debit and Credit columns**, so equal total debits and credits are visible.
   Netting the total would always read 0 / 0.
2. **Wizard filters in report options.** They travel under `azk_tb` and survive every
   re-render. Journals and prefixes become a `forced_domain`.
   - Prefixes are validated so they cannot inject `=like` wildcards.
   - With a prefix filter, *Undistributed Profits/Losses* appears only when a prefix
     matches the company's unaffected-earnings account. It is then computed without the
     prefix, because it aggregates P&L accounts.
3. **Analytic filter = proportional share.** An entry split 60/40 between two analytic
   accounts shows 60 % under the first. This reuses the engine's analytic shadow table,
   the same logic as Odoo's analytic group-by.
   - Accounts without analytic distribution (bank, receivables, payables, taxes) are not
     part of an analytic view, so **a filtered report is intentionally unbalanced**. A
     notice says so on screen, in the PDF and in the XLSX.
   - Analytic lines exist only for posted entries.
4. **One line per account and company.** With several companies selected, Odoo's default
   *consolidation* regroups the report by account code, hiding the real accounts. It is
   turned off here, because prefixes, hierarchy, currencies and skip-zero all work on real
   account lines. The figures equal the native report with consolidation off.

### 3.4 Demo data

Installing with `--with-demo` runs an idempotent loader. It is written in Python so that
account codes, journals and fiscal-year dates fit any database. It creates:

- a 3-level account tree (`1000 › 1100 › 1110/1120`, `6000 › 6100/6200`, …);
- two foreign currencies with rates;
- an analytic plan with two departments and a salary entry split 60/40;
- posted entries across the previous and the current fiscal year;
- one draft and one cancelled entry.

### 3.5 Testing strategy

**Principle.** Odoo's own Trial Balance is the reference dataset. Every account's initial,
debit, credit and end values must match it. Comparing totals alone is not enough, because
offsetting errors would hide. Every test was seen failing before the code existed.

**Automated tests (51):**

| File | Covers |
|---|---|
| `test_report_engine.py` | Per-account parity with native Odoo. Classic split. Reversed-sign account. Opening-only account. P&L across fiscal years (Undistributed P/L). Last day of the period / the day before. Parent net-split and grand total. Multi-company isolation. Drafts included or excluded; cancelled entries never included. Default options with several companies and *totals below sections*. |
| `test_report_filters.py` | Journal and multi-prefix filters, with parity against native under the same domain. Prefix + Undistributed P/L rule. Analytic 60/40 share. Unbalanced notice. Prefix injection attempt (`1%' OR 1=1`). |
| `test_report_display.py` | Skip-zero keeps cancelling movements and drops empty parents. Hierarchy levels 1–3 keep totals. Amount-currency lines add up to the account and show their symbol. Parents never sum mixed currencies. Column hidden when off. |
| `test_wizard.py` | Field-to-options mapping. Options survive re-render. Preview action. Date validation. Single-plan analytic validation. Access rights. |
| `test_exports.py` | XLSX header, values equal to the report, bold total, analytic notice. PDF header and export path. The wkhtmltopdf call is stubbed because, inside a test transaction, it would fetch its CSS from the blocked server. Real PDF and XLSX files were also generated from the demo database. |
| `test_review_fixes.py` | Regressions from the independent review. Unfolded sub-lines never inflate the total. Expanding one account adds no Undistributed P/L lines. Prefixes with `-`. Invalid prefixes rejected. No comparison periods. |
| `test_report_filter_bar.py` | Filter bar registered, PDF/XLSX buttons, native journal filter. **Tour:** every switch, the prefix field and the level selector update the report. |
| `test_demo_data.py` | Demo loader content and idempotency. Parity with native over the demo data, with and without hierarchy. Total debit = total credit. |

**Reconciliation with the native Trial Balance (demo data).** This table was generated by
[`scripts/reconcile_tb.py`](azk_dynamic_trial_balance/scripts/reconcile_tb.py), not typed by
hand.

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
| **Total** | 0.00 | 0.00 | 266,638.24 | 266,638.24 | 266,638.24 | 266,638.24 | 0.00 | 0.00 | **0.00** |

Lines only in ours: none. Largest difference: 0.00. Re-run it with:

```bash
python odoo-bin shell -c <your.conf> -d <db> --no-http < azk_dynamic_trial_balance/scripts/reconcile_tb.py
```

**Manual test script** (database installed with `--with-demo`):

| # | Steps | Expected result |
|---|---|---|
| 1 | Open *Dynamic Trial Balance*, keep the default dates, press **Preview**. | The demo tree with Initial / Movement / End × Debit / Credit / Balance. The total line has equal Debit and Credit in Initial and End. |
| 2 | Open the native *Trial Balance* for the same period. Compare `1110 Main Bank (Demo)` and `6100 Salaries (Demo)`. | Identical initial, movement and end balances. |
| 3 | Wizard › *Accounts* `11` › Preview. | Only `11xx` accounts, with the filter banner. |
| 4 | Wizard › *Analytic Accounts* `Sales Dept (Demo)` › Preview. | Salaries movement **4,800** (60 % of 8,000), and the "not balanced" notice. |
| 5 | Wizard › *Hierarchy Only Parents*, level **1** › Preview. | Only the top accounts, with the same total as step 1. |
| 6 | Wizard › *Show Amount Currency* › Preview. | `1200 Customers (Demo)` split into a company-currency line and a foreign-currency line showing its amount in that currency. |
| 7 | Wizard › **PDF** and **XLSX**. | The same lines and numbers as the Preview, with company, period and filters in the header. |

### 3.6 Known limitations

- Single period by design: the native *Comparison* filter is not offered.
- With *Unfold All*, the native report omits its *Cumulative Translation Adjustment* line
  in multi-currency companies. This report inherits that behaviour.
- With an analytic filter, *Amount Currency* shows the journal item's full foreign amount,
  because the analytic shadow table carries `amount_currency` unprorated.
- The engine's trial-balance query method is re-declared in the handler to add an
  `amount_currency` aggregate, because the native SELECT is built inline. Its logic is
  otherwise identical, and the parity tests guard it.
- With *Show Amount Currency*, Debit/Credit splits are per currency line, so total
  Debit/Credit can differ from the report with the option off. Net balances are identical.

---

## 4. Exercise 3 — POS Enhancements

The exercise is split into two independent modules, as required. Each feature is toggled
per POS, and with both toggles off the POS behaves exactly as native Odoo.

### 4.1 Salesperson Assignment (`azk_pos_salesperson`)

**Specified features**

- **Salesperson model** (`pos.sale.person`, *Point of Sale › Configuration › Salespersons*):
  name (required), phone, optional related employee. Records can be archived and belong to a
  company.
- **Per-POS settings**, on the POS form and the POS Settings page:
  `active_salesperson_feature` and `allowed_sale_person_ids`.
- **Offline.** The allowed salespersons are loaded with the POS data. Assignments are stored
  on the order and synced with it, with no extra server calls.
- **Line assignment.** A salesperson button under every order line (the name, or *Add
  salesperson*) changes **that line only**.
- **Order assignment.** **Assign Salesperson to Order** assigns a salesperson to **every
  line** and also becomes the order salesperson.
  - **Lines added afterwards inherit it.**
  - A line changed individually keeps its value.
  - Pressing the button again overwrites all lines (assessment test case 3).
- **Popup.** The native selection popup, listing the allowed salespersons plus **No
  salesperson**, which clears the value.
- **Backend.** `salesperson_id` appears in both order-line list views and on the order
  form.
- **Receipt.** `Salesperson: <name>` is printed under the product, only when the feature is
  on and the line is assigned. This applies to the client receipt and to the server receipt
  (email/download).

**Assignment rules**

- A product added again merges only into a line credited to the same salesperson, so two
  salespersons selling the same product keep separate lines.
- Combo children follow their parent.
- Refund lines keep the original seller.

### 4.2 Enhanced Receipt Layout (`azk_pos_enhanced_receipt`)

- **Per-POS settings:** `use_customized_receipt`, `receipt_logo`, `company_name`,
  `company_details`, `show_customer_details`.
- **Enhanced layout**, top to bottom, with sections separated by dashed rules:
  1. The receipt logo, or the standard logo when none is uploaded. Odoo's *Your logo*
     placeholder is never printed.
  2. Company name (large), details and tax ID.
  3. Order block: ticket, date, cashier.
  4. Customer name and address, when enabled.
  5. An HTML **table**: Product | Qty | Price | Total.
     - Product names are bold at normal size, so they do not wrap on an 80 mm ticket.
     - Numbers sit in narrow right-aligned columns.
     - Secondary lines (salesperson, discount, note) are small and muted.
     - The gift/basic receipt shows Product | Qty only.
  6. Totals, taxes, payments and footer, as native.
- **No duplicates.** The native ticket, cashier, customer and company blocks are replaced,
  not repeated.
- **Email rendering.** The layout uses tables, not flexbox, so the emailed image rendered by
  wkhtmltoimage looks the same as the printed receipt.
- **Option off.** The native receipt, unchanged (backward compatible).
- **Security.** `company_name` and `company_details` are `Html` fields with Odoo's sanitizer.
  Scripts and event handlers are stripped on save, so nothing executable reaches the
  receipt.

### 4.3 Beyond the specification

These were added after hands-on acceptance testing. Each can be configured or ignored
without affecting the specified behaviour.

- **Salesperson prompt on the first product.** Adding the first product of an order opens
  the salesperson popup. The person chosen becomes the order salesperson, so every product
  added afterwards gets the same person.
  - *No salesperson* skips the prompt for that order.
  - Closing the popup is not an answer: the next product asks again.
  - Refunds and lines added by code (global discount, tips, sale-order import) never ask.
- **Receipt preview on the payment screen** (`azk_payment_receipt_preview`, on by default).
  On large screens the payment screen shows the receipt exactly as it will print, updated
  live as payments are added.
- **Automatic receipt email** (`azk_auto_email_receipt`). After *Validate*, the receipt is
  emailed when the customer has a valid email address.
  - It uses the native `action_send_receipt`, does not block the cashier, and confirms
    with a notification.
  - Orders that are still offline are skipped. Requires an outgoing mail server.
- **Printing without a click** uses Odoo's native *Automatic Receipt Printing*
  (`iface_print_auto`).
- **Salesperson reports** (*Point of Sale › Reporting*, POS managers):
  - **Sales by Salesperson.** Every product sold, credited to the salesperson of its line,
    built on the native POS analysis so the amounts reconcile with it.
    - Pivot: salesperson → product → day. Also a graph and a detailed list.
    - Measures: orders, quantity, sales with and without tax, discount, margin, commission.
    - Filters: completed sales (default), refunds, unassigned sales, dates, POS, session.
  - **Salesperson Performance.** One row per order and salesperson: orders, sales,
    **average order value**, items and commission, by day, week or month. Refunds reduce
    sales but are not counted as orders.
  - **Commission.** A rate (%) per salesperson, applied to sales excluding tax.
    - The rate is frozen on each sale line at the time of sale, so a later change never
      rewrites past commissions.
    - A refund uses the rate of the sale it refunds.
    - Set it in *Point of Sale › Configuration › Salespersons › Commission (%)*.

### 4.4 Configuration and testing

**Demo data** creates *Salesperson A, B, C*. For the assessment's configurations (§4.1),
open *Point of Sale › Configuration › Point of Sale* and set up:

| POS | Salesperson Assignment | Allowed | Customized Receipt | Receipt fields |
|---|---|---|---|---|
| `POS_Sales_Enabled_Enhanced_Receipt` | ✓ | A, B | ✓ | logo, company name/details, customer details ✓ |
| `POS_Sales_Enabled_Default_Receipt` | ✓ | A, B | ✗ | — |
| `POS_Sales_Disabled_Enhanced_Receipt` | ✗ | — | ✓ | logo, company name/details, customer details ✓ |
| `POS_All_Disabled` | ✗ | (may be set; ignored) | ✗ | (may be set; ignored) |

**Manual test script** (assessment §4.2):

| # | Test case | Steps | Expected result |
|---|---|---|---|
| 1 | Visibility | Open a session on each POS and complete a sale. | Salesperson controls appear only when Salesperson Assignment is on. The table layout appears only when Customized Receipt is on. |
| 2 | Per line | Add *X* (choose *No salesperson* in the first-product prompt) and *Y*. Assign A to X and B to Y with the line buttons. Pay. | A under X and B under Y on screen, on the receipt and in *Orders › Order lines*. |
| 3 | Global overwrites | Assign A and B per line, then *Assign Salesperson to Order* → C. | Both lines show C on screen, on the receipt and in the backend. |
| 4 | No assignment | Sell without assigning anyone. | No name anywhere; empty column in the backend. |
| 5 | Change during a session | Enable both features on the POS of an open session and sell without reloading. | UI and receipt unchanged until the POS is reloaded (expected POS behaviour). |

**Automated tests (77, both modules installed).** Every test was seen failing first. The
browser tours drive Chrome through real sales.

| File | Covers |
|---|---|
| `azk_pos_salesperson/tests/test_salesperson_backend.py` | Required name. Only the allowed salespersons are loaded, and none when the feature is off. Order sync stores the line and order salesperson. Access rights. Backend views. |
| `azk_pos_salesperson/tests/test_salesperson_receipt.py` | Name under the product on the receipt data and the server receipt. Hidden when the feature is off or the line is unassigned. |
| `azk_pos_salesperson/tests/test_salesperson_ui.py` | **Tours:** test cases 2, 3 and 4. First-product prompt (choose or skip). Inheritance of the order salesperson. Merge rule. Combo children. Assignments survive a browser refresh. UI hidden when off. |
| `azk_pos_salesperson/tests/test_salesperson_report.py` | Commission bounds, frozen at sale time, kept on re-sync and refunds. Report totals per salesperson; refunds netted; unassigned group. Performance rows, average order value, refunds not counted, company rule. Menus and views. |
| `azk_pos_salesperson/tests/test_review_fixes.py` | Independent-review regressions. Editing a combo keeps its children credited. Refunds keep the salesperson. Order button on small screens. Multi-company. Employees never loaded into the POS. |
| `azk_pos_enhanced_receipt/tests/test_enhanced_backend.py` | Fields. HTML sanitizing (`<script>`, `onerror`). Form and settings views. No clash with native fields. |
| `azk_pos_enhanced_receipt/tests/test_enhanced_receipt.py` | Enhanced layout. Native layout when off. Customer hidden. Logo fallback. Basic receipt table. No duplicated company info. |
| `azk_pos_enhanced_receipt/tests/test_checkout.py` | Payment-screen preview and automatic email. |
| `azk_pos_enhanced_receipt/tests/test_both_modules.py` | Salesperson printed once, inside the enhanced table. **Tours:** test case 1 on the four configurations and test case 5, each checking the client-rendered receipt. |

### 4.5 Conflicts when both POS modules are installed

*Assessment question: "If both addons are installed on the same database instance, what
possible conflicts might occur, and how could we resolve them?"*

Both modules extend the **same receipt** and the **same POS settings**. These are the
possible conflicts and how this design avoids them:

1. **The same QWeb receipt templates are extended twice.**
   - The salesperson module only appends inside the native `extra-info` hook of
     `pos_orderline_receipt_information`.
   - The enhanced receipt replaces the line loop with a table, but its Product cell
     **re-uses** `pos_orderline_receipt_information`.
   - The salesperson name therefore appears inside the table with no dependency between
     the modules. `test_both_modules.py` verifies it.
   - **Rule:** target stable, named hooks, and never replace a template that another addon
     extends.
2. **Both patch the receipt data generator** (JS `GeneratePrinterData` and its Python
   mirror). Each patch calls `super()` and adds only its own keys (`azk_salesperson`,
   `azk_enhanced`, …).
3. **Both add settings to the same views.** Each uses its own `<setting id>`, positioned
   relative to native anchors.
4. **Field name clashes.** The new `pos.config` fields do not exist natively (tested).
   Native `custom_logo` and `logo` are untouched.
5. **Load order.** Neither module depends on the other. If two addons ever needed tighter
   cooperation, the standard resolution is a small **bridge module** (`auto_install: True`,
   depending on both) that holds the glue code. This design does not need one.

---

## 5. Assumptions and deviations

| Topic | Specification | Decision and reason |
|---|---|---|
| Odoo version | Exercise 3 targets Odoo 18. | All modules target the installed Odoo 20.0 Enterprise. Every API was verified in its source. |
| Receipt template | `point_of_sale.XmlReceipt` | No longer exists. The Odoo 20 receipt is server QWeb rendered on the client, so the extensions target `pos_order_receipt*`. |
| Access rights | — | Odoo 20's `ir.access` format; global domain lines replace record rules. Binary fields are `BinaryBytes`. |
| Journals / Analytic Accounts | Described as Many2one, with "if nothing is selected". | Implemented as multi-selection (Many2many). Analytic accounts are limited to one plan, so the shares stay meaningful. |
| Company name / details | `Text` | `Html` with sanitizing, because the specification allows HTML and it must not run scripts. |
| Global assignment | Overwrites individual assignments (test case 3). | Implemented as specified. Lines added afterwards inherit the order salesperson. |
| Settings placement | POS form | On both the POS form and the POS Settings page. |
| Archived salespersons | — | Stay on past orders and in reports. They are no longer offered in the POS. |

---

## 6. Engineering process and GenAI usage

The work used Claude Code (model Claude Opus 5.5) under a written engineering protocol:
**analyse → plan → implement → test → debug → review → verify**, with no claim made
without evidence.

- **Design first.** Each feature has a written design ([`docs/superpowers/specs`](docs/superpowers/specs))
  and a test-first plan ([`docs/superpowers/plans`](docs/superpowers/plans)). A second agent
  checked each design before the plan was written.
- **Test-first.** Every test was seen failing before the code. Some fixes were also proven
  with deliberate mutations.
- **Independent review.** A fresh agent reviewed each whole branch before merging. Its
  important findings were fixed test-first.
- **Verification in the source.** Framework claims were checked against the installed
  Odoo 20 code.

| Document | Content |
|---|---|
| [`docs/genai/prompts.md`](docs/genai/prompts.md) | The prompts that directed the work, the skills and agents used, and token usage. |
| [`docs/genai/prompt-log.md`](docs/genai/prompt-log.md) | What the AI produced for each step, and what it found along the way. |

**Token usage:** about **419 million tokens** processed over 1,142 model requests: 0.85 M
output, 4.97 M fresh input and 413 M cached context. The breakdown is in
[`prompts.md`](docs/genai/prompts.md#6-token-usage).
