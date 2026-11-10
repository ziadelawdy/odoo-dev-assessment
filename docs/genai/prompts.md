# Prompt Engineering Log

These are the prompts that directed the work, in the order they were issued. The wording
has been edited for readability. The intent, constraints and decisions are as given.
Routine conversational turns are left out: confirmations, progress checks and merge
approvals. What the assistant produced for each step is summarised in
[`prompt-log.md`](prompt-log.md). The design documents and implementation plans are in
[`docs/superpowers`](../superpowers).

| | |
|---|---|
| **Assistant** | Claude Code (Anthropic) |
| **Model** | Claude Opus 5.5 (`claude-opus-5-5`), for the main session and every subagent |
| **Target** | Odoo 20.0 Enterprise (`20.0+e-20261105`), installed source used as the reference |
| **Method** | Spec → plan → test-first implementation → independent review → verification |

## Contents

1. [Engagement setup](#1-engagement-setup) — P1–P3
2. [Exercise 2: Dynamic Trial Balance](#2-exercise-2-dynamic-trial-balance) — P4–P12
3. [Exercise 3: POS Enhancements](#3-exercise-3-pos-enhancements) — P13–P18
4. [Release](#4-release) — P19–P21
5. [Skills and agents used](#5-skills-and-agents-used)
6. [Token usage](#6-token-usage)

---

## 1. Engagement setup

### P1 — Requirements analysis

```text
ROLE
Senior Odoo developer performing a pre-implementation review of a technical assessment.

INPUT
"Odoo Dev Assessments.pdf" (attached).

TASK
Analyse the document end to end and produce:
1. Requirements: a precise, testable checklist per exercise covering fields, behaviours,
   outputs, test cases and documentation obligations.
2. Specification gaps: ambiguities, contradictions and missing artefacts (for example a
   referenced mockup that is not included, or a field type that contradicts the described
   behaviour).
3. Technical risks: version drift between the specification and the target Odoo version,
   security exposure, and framework behaviour that affects the design.

CONSTRAINTS
- Analysis only. No code, no scaffolding.
- Separate facts stated in the document from your own inferences.

OUTCOME
A brief I can use to choose two exercises and to record the assumptions.
```

### P2 — Scope and environment

```text
DECISION
Deliver Exercise 2 (Dynamic Trial Balance) and Exercise 3 (POS Enhancements).

TARGET
The Odoo 20.0 Enterprise instance installed on this machine. Exercise 3 references Odoo 18.
Implement for Odoo 20 and record the deviation and its consequences in the README.

ENVIRONMENT RULES
- Create a new, dedicated Git repository.
- Use a separate configuration, port and databases for development and tests.
- Do not modify, restart or write to any existing Odoo service, database or configuration
  file on this machine.
```

### P3 — Engineering protocol (applies to every subsequent task)

```text
ROLE
Operate as a senior software architect, senior Python developer, Odoo 20 technical expert,
security auditor and independent code reviewer. The objective is reliable, maintainable,
secure, production-grade code whose compatibility has been verified.

1. TOOLING
   Before each task, find the skills and tools available in this environment and use the
   relevant ones: planning, test-driven development, systematic debugging, code review and
   verification before completion. Never report a tool as used unless it was invoked. If a
   capability is unavailable, say so and use the strongest available alternative.

2. ANALYSIS BEFORE CODE
   Inspect the project structure, exact framework version, dependencies, conventions and
   existing tests. Do not assume any method, field, API or module exists: verify it in the
   installed Odoo 20 source before relying on it.

3. LIFECYCLE
   ANALYSE → PLAN → IMPLEMENT → TEST → DEBUG → REVIEW → VERIFY.
   Every plan states the files affected, dependencies, risks, required tests and expected
   behaviour.

4. IMPLEMENTATION STANDARDS
   Clean architecture, explicit error handling, secure defaults, minimal complexity,
   backward compatibility. No changes to unrelated code.

5. EVIDENCE
   Run the tests. Never claim a test passed without its output.

6. SAFETY
   No destructive database operation without my explicit approval. Never expose credentials.

7. REPORTING
   Close every task with a status report: what was delivered, how it was verified, and what
   remains open or is a known limitation.
```

---

## 2. Exercise 2: Dynamic Trial Balance

### P4 — Kick-off

```text
Start with Exercise 2. Apply the engineering protocol.
First analyse the native Odoo 20 Trial Balance: its handler, its query and its options.
Then propose an architecture. Do not write code until the design is approved.
```

### P5 — Acceptance criteria

```text
OBJECTIVE
A reviewer must conclude that the developer understands Odoo accounting, not only the
Odoo UI. Treat the following as binding acceptance criteria and as the test strategy.

ACCOUNTING CORRECTNESS
- Figures must equal the native Trial Balance under identical filters, account by account:
  opening debit/credit, period debit/credit and closing debit/credit. Totals alone are
  not acceptable evidence, because errors can offset each other.
- Keep opening balance (before the period start), period movement (within the period) and
  closing balance (opening plus movement) separate.
- Respect how Odoo treats opening entries and the carry-forward of prior-year results
  (undistributed profit/loss).
- Use account.move.line under Odoo's accounting rules: account types, receivable/payable,
  income/expense, equity, multi-company, multi-currency, posted versus draft entries and
  date filters.

ENGINEERING
- Prefer the ORM and the Enterprise accounting report engine to rebuilding Trial Balance
  logic.
- Enforce company and access rules. No unnecessary sudo(). No ad-hoc SQL that bypasses
  Odoo security.

PROOF
- A reconciliation table (Account | Odoo closing | Custom closing | Difference) in which
  every difference is zero, generated by a script rather than typed.
- Automated tests for: a period without movement, an account with only an opening
  balance, an entry on the last day of the period, an account with a reversed sign, several
  companies, and posted versus draft entries.
- Every remaining difference documented with its root cause.

ANTI-PATTERNS TO AVOID
Wrong figures in a polished layout. A single balance column used for everything. A missing
opening balance. Ignored prior years. Ignored posting state. Data leaking across companies.
No tests.
```

### P6 — Column presentation

```text
Present Initial Balance and End Balance as separate Debit and Credit columns, as in a
classic trial balance, not as a single signed balance. A net debit balance goes to Debit,
a net credit balance goes to Credit, and Balance = Debit − Credit.
```

### P7 — Analytic filter semantics

```text
When analytic accounts are selected, report only the share of each journal item that is
allocated to them. Example: a line distributed 60 % to the selected analytic account
contributes 60 % of its amount, not 100 %. This must match Odoo's analytic distribution
logic. If the filtered report no longer balances, say so explicitly in the output.
```

### P8 — Design approval

```text
The design is approved. Produce the implementation plan: small test-first tasks, each
with the files it touches, its interfaces, the tests that prove it and the expected
results.
```

### P9 — Execution mode

```text
Execute every task in the plan. When all tasks are complete, have an independent reviewer
review the whole branch. Fix every critical and important finding test-first, then report
the results and the deferred minor findings.
```

### P10 — User acceptance testing

```text
Before starting the next exercise, I will run user acceptance testing myself. Assume the
tester is not an accountant.

Provide a step-by-step test script for the demo database. For each step give:
- the exact menu path;
- the inputs to enter;
- the expected result, with expected figures wherever possible.

If a required application (Accounting) is missing, install it on our test database only.
```

### P11 — Defects from acceptance testing

```text
UAT findings:
1. Scenario 3: total debit does not equal total credit, although balanced totals were
   stated as an expected result.
2. Scenario 4: amounts are displayed in USD.

For each finding, decide whether it is expected behaviour or a defect and explain why.
If it is a defect, reproduce it with a failing test before fixing it. Then confirm whether
any further test is needed before the module is accepted.
```

### P12 — In-report filtering

```text
CHANGE REQUEST
Filters can currently be set only in the wizard. Comparable solutions let users change
filters directly in the report (reference attached).

REQUIREMENTS
- Add a filter bar to the report itself, using the same component mechanism as native
  Odoo accounting reports.
- Every change reloads the report immediately and survives a page refresh.
- PDF and XLSX exports must always match what is on screen.
- Cover the filter bar with a browser tour.
```

---

## 3. Exercise 3: POS Enhancements

### P13 — Kick-off and assignment rules

```text
Start Exercise 3. Apply these business rules for salesperson assignment:

1. ASSIGN TO ORDER
   Selecting a salesperson for the order assigns them to every existing line. Every line
   added afterwards inherits them automatically.
2. ASSIGN TO LINE
   A salesperson set on one line applies to that line only and is not inherited by new
   lines.
3. MANUAL OVERRIDES PERSIST
   If a line is reassigned (for example from Ahmed to Mohamed), the change is kept. Adding
   products never overwrites it. Using "assign to order" again does overwrite every line.

Use the assessment's test cases verbatim as acceptance tests. Present the design with a
mockup of the original and enhanced receipts for approval before implementation.
```

### P14 — Design approval and execution

```text
The design is approved. Write the plan, then execute it task by task in this session,
test-first, with one independent review of the whole branch at the end.
If browser tours need an additional Python package, install it in an isolated,
git-ignored directory. Do not install anything system-wide.
```

### P15 — UX defect and first-product flow

```text
UAT FINDINGS (POS)
1. The per-line salesperson control is not visible. Find the root cause.
2. Workflow change: when the first product is added to a new order, prompt for the
   salesperson. Apply that choice to every product added afterwards, and keep both
   options available: change all lines at once, or change one line at a time.

CONSTRAINTS
- Refund orders and lines added programmatically (global discount, tips, sale-order
  import) must never trigger the prompt.
- Cover the new flow with browser tours that fail before the change.
```

### P16 — Checkout and receipt redesign

```text
UAT FINDINGS (CHECKOUT)
1. Show the receipt on the payment screen while the customer is paying, updated live.
2. Print the receipt automatically, and email it automatically when the customer has a
   valid email address.
3. Modernise the receipt layout. Present several design options as mockups before
   implementing.

CONSTRAINTS
- Keep the products table required by the assessment.
- Reuse native mechanisms (automatic receipt printing, the receipt email action) instead
  of reimplementing them.
- Each behaviour is configurable per POS.
```

### P17 — Salesperson sales report

```text
OBJECTIVE
A report for reviewing salesperson performance: exactly what each salesperson sold, by
product, by day and by any other useful dimension.

REQUIREMENTS
- Build on Odoo's native POS sales analysis so the figures reconcile with it.
- Net refunds against sales.
- Show sales without a salesperson as their own group.
- Default to completed sales only.
- Enforce multi-company access rules.

ALSO
Propose additional metrics a sales manager would value. I will select which to include.
```

### P18 — Scope of extras

```text
Include:
1. A commission rate per salesperson, applied to sales excluding tax. The rate is frozen
   on each sale line at the time of sale, so a later rate change never alters past
   commissions. A refund uses the rate of the sale it refunds.
2. Order count and average order value per salesperson. Refund orders reduce sales but
   do not count as orders.

Exclude the PDF statement and the smart button.
```

---

## 4. Release

### P19 — Handover

```text
Write a functional handover of everything delivered: what each module does, where each
feature is in the menus, and how to configure it (for example, where the commission rate
is set). Write it for a business user, not a developer.
```

### P20 — Compliance audit

```text
Audit the repository against the assessment PDF item by item: features, README sections
(features, installation, configuration, testing strategy), demo data, the GenAI log and
the question about conflicts between the two POS modules. List every gap before
submission. Do not report an item as complete without evidence.
```

### P21 — Publication

```text
Publish the repository to github.com/ziadelawdy/odoo-dev-assessment (public).
Verify that the remote main matches the local main and that the README is reachable
without authentication.
```

---

## 5. Skills and agents used

The protocol in P3 required the assistant to use the available skills for real. These were
invoked during the project:

| Skill | Used for |
|---|---|
| `superpowers:using-superpowers` | Choosing the right skill at the start of each task. |
| `superpowers:brainstorming` | Turning each request into an approved design: questions, mockups, a written spec, and a "builder check" by a second agent. |
| `superpowers:writing-plans` | Turning each approved design into a test-first implementation plan with interfaces and a review focus. |
| `superpowers:executing-plans` | Executing the plans task by task, keeping a progress ledger and recording every deviation as a ruling. |
| `superpowers:test-driven-development` | Writing each test first and watching it fail before writing the code. Some fixes were also proven by deliberate mutations. |
| `superpowers:requesting-code-review` | An independent whole-branch review by a fresh agent before each merge. |
| `superpowers:verification-before-completion` | Claiming nothing without running the command and reading its output. |
| `superpowers:finishing-a-development-branch` | Re-running the suite on the merged result before integrating each branch. |

| Agent | Used for |
|---|---|
| `Explore` | Mapping the Odoo 20 extension points across the installed source (report engine, POS store, receipt pipeline). |
| `general-purpose` | Builder checks on the designs, and the independent code reviews. |

## 6. Token usage

Counted from the session logs, main sessions and subagents included, with every model
response counted once.

| Measure | Tokens |
|---|---:|
| Output (generated by the model) | 851,667 |
| Fresh input (new context sent to the model) | 4,973,695 |
| Cached input (context re-read from the prompt cache) | 413,173,588 |
| **Total processed** | **418,998,950** |
| Model requests | 1,142 |

Most of the total is cached input. In a long agentic session, each step re-reads the
conversation and source files from the prompt cache.
