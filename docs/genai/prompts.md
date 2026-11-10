# Prompts used

This file lists the prompts I gave the AI assistant (Claude Code, model Claude Opus 5.5),
in the order I gave them. I wrote them in Egyptian Arabic. The versions below are English
translations, edited into a clean, professional form. Each one keeps the intent, the
constraints and the decisions of the original.

Short conversational replies are left out: "continue", "in Arabic please", progress
questions, and button answers such as "Merge". The design and plan documents each prompt
produced are in [`docs/superpowers`](../superpowers). What the AI did with each prompt is
summarised in [`prompt-log.md`](prompt-log.md).

---

## 0. Setup

### P1 — Requirements analysis

> You are a senior Odoo developer reviewing a technical assessment before any code is
> written. Study the attached PDF (*Odoo Dev Assessments.pdf*) end to end and report:
>
> 1. What each exercise requires, as a precise checklist of fields, behaviours, outputs,
>    tests and documentation.
> 2. Gaps, ambiguities and contradictions in the specification, such as a missing mockup,
>    undefined fields or a field type that does not match the described behaviour.
> 3. Technical risks: version differences, security issues and behaviour of the target
>    Odoo version.
>
> Do not start implementing. We will pick two exercises after this analysis.

### P2 — Scope

> We will deliver **Exercise 2 (Dynamic Trial Balance)** and **Exercise 3 (POS
> Enhancements)**. Target the Odoo 20.0 Enterprise instance installed on this machine,
> even though Exercise 3 mentions Odoo 18. Record that deviation in the README. Create a
> new, separate Git repository. Do not touch my existing Odoo services, databases or
> configuration.

### P3 — Development protocol (applies to every task)

> Act as a senior software architect, senior Python developer, Odoo 20 technical expert,
> security auditor and independent code reviewer. The goal is reliable, maintainable,
> secure, production-quality code whose compatibility has been verified.
>
> 1. **Tools.** Before each task, find the skills and tools available in this environment
>    and actually use the relevant ones: planning, test-driven development, systematic
>    debugging, code review and verification before completion. Never claim a tool ran
>    unless it did. If a tool is unavailable, say so and use the best alternative.
> 2. **Analyse before you code.** Inspect the project structure, the framework version,
>    dependencies, conventions and existing tests. Never assume a method, field, API or
>    module exists: verify it in the installed Odoo 20 source.
> 3. **Workflow.** Follow *Analyse → Plan → Implement → Test → Debug → Review → Verify*.
>    Every plan names the files to change, the dependencies, the risks, the required
>    tests and the expected behaviour.
> 4. **Code.** Clean architecture, proper error handling, secure by default, minimal
>    complexity. Do not modify unrelated code.
> 5. **Testing.** Run the tests for real. Never report a test as passing without its
>    output.
> 6. **Safety.** Never run destructive database operations without my explicit approval.
>    Never expose credentials.
> 7. **Reporting.** End each task with a status report: what was done, how it was
>    verified, and what remains or is a known limitation.

---

## 1. Exercise 2 — Dynamic Trial Balance

### P4 — Start

> Start with the Dynamic Trial Balance. Follow the protocol: analyse the native Odoo 20
> Trial Balance first, then propose a design before writing any code.

### P5 — Acceptance criteria

> The reviewer must conclude that the developer understands Odoo accounting, not only
> Odoo screens. Treat the following as the acceptance criteria and the test strategy.
>
> **Correctness**
> - The numbers must equal the native Trial Balance under the same filters, account by
>   account: opening debit/credit, period debit/credit and closing debit/credit.
>   Comparing totals alone is not acceptable, because errors can cancel each other out.
> - Keep these separate: **opening balance** (everything before the period start),
>   **period movement** (inside the period) and **closing balance** (opening plus
>   movement). Respect how Odoo handles opening entries and the carry-forward of prior
>   years' results (undistributed profit/loss).
> - Build on `account.move.line` and Odoo's accounting rules: account types,
>   receivable/payable, income/expense, equity, multi-company, multi-currency, posted
>   versus draft entries, and date filters.
>
> **Engineering**
> - Use the ORM and the Enterprise accounting report engine where they fit, instead of
>   rebuilding Trial Balance logic from scratch.
> - Respect company and access rules. Avoid unnecessary `sudo()` and ad-hoc SQL that
>   bypasses Odoo's security.
>
> **Proof**
> - Provide a reconciliation table (Account | Odoo closing | Custom closing |
>   Difference) where every difference is zero.
> - Automated tests for: a period with no movement, an account with only an opening
>   balance, an entry on the last day of the period, an account with a reversed sign,
>   several companies, and posted versus draft entries.
> - Document every remaining difference and its cause.
>
> Signs of shallow work, all to be avoided: wrong numbers in a polished layout, a single
> balance column used for everything, a missing opening balance, ignored prior years,
> ignored posted/draft status, data leaking across companies, and no tests.

### P6 — Column layout

> Show Initial Balance and End Balance as separate Debit and Credit columns, like the
> classic trial balance, not as a single signed balance.

### P7 — Analytic filter rule

> When an analytic account is selected, report only the share of each journal item that
> belongs to it. For example, if a line is distributed 60 % to the selected analytic
> account, report 60 % of the amount, not the full amount. This matches Odoo's analytic
> distribution logic.

### P8 — Approve the design

> The design is approved. Write the implementation plan: small, test-first tasks, each
> with its files, interfaces, tests and expected results.

### P9 — Execution mode

> Execute every task in the plan. At the end, have an independent reviewer check the
> whole branch, and fix the important findings test-first before reporting back.

### P10 — Manual acceptance before moving on

> Before we start the next exercise, I want to test the module myself. I am not an
> accountant. Give me a step-by-step manual test script on the demo database. For each
> step, give the exact menu path, what to enter and the result I should see, with
> expected numbers where possible. If a required module (Accounting) is missing,
> install it on our own test database only.

### P11 — Feedback from the manual test

> Results from the manual test:
> - In test 3, debit and credit are not equal, although you said they would balance in
>   one of the tests. Explain whether this is expected. If it is a bug, fix it test-first.
> - Test 4 shows amounts in USD. Confirm this is the intended currency behaviour.
>
> Then tell me whether any other test is needed before we call the module done.

### P12 — Filters inside the report

> While testing, I noticed the filters can only be set in the wizard. Peers' solutions
> let the user change filters directly in the report (example attached). Add a filter
> bar to the report itself, using the same mechanism as native Odoo reports. Every
> change must reload the report and survive a page refresh. Keep PDF and XLSX export
> consistent with what is on screen.

---

## 2. Exercise 3 — POS Enhancements

### P13 — Start, with the salesperson assignment rules

> Start Exercise 3. Apply these business rules for salesperson assignment:
>
> 1. **Assign to order.** When the cashier picks a salesperson for the whole order, every
>    existing line gets that salesperson, and every line added afterwards inherits them
>    automatically.
> 2. **Assign to line.** A salesperson set on a single line applies to that line only and
>    is not inherited by new lines.
> 3. **Manual changes stick.** If the cashier changes one line from Ahmed to Mohamed,
>    that change is kept. Adding new products must not overwrite it. Using *assign to
>    order* again does overwrite every line.
>
> Use the assessment's test cases verbatim as acceptance tests. Write the design with a
> mockup of the receipt (original versus enhanced) for my approval.

### P14 — Approve and execute

> Design approved. Write the plan, then execute it task by task in this session with
> test-first development, and run one independent review of the whole branch at the
> end. If tours need an extra Python package, install it in an isolated, git-ignored
> folder.

### P15 — Usability feedback: assignment flow

> From manual testing in the POS:
> - I cannot find the per-product salesperson control. Investigate why it is not
>   visible.
> - When I add the first product to a new order, ask me who the salesperson is. Apply
>   that choice to every product I add afterwards, but still let me change all lines at
>   once or one line at a time.
>
> Keep refunds, and lines added by code (discounts, tips, imported sale orders), out of
> this prompt. Cover the new flow with tours that fail before the change.

### P16 — Checkout and receipt

> Second round of manual-testing feedback:
> - Show the receipt on the payment screen while the customer is paying.
> - Print the receipt automatically, and email it automatically when the customer has an
>   email address.
> - Make the receipt cleaner and more modern. Show me a few design options as mockups
>   before implementing.
>
> Keep the assessment's required products table. Reuse native Odoo mechanisms (automatic
> printing, the receipt email action) instead of reimplementing them.

### P17 — Salesperson sales report

> Build a report I can use with the salespeople: exactly what each one sold, by product,
> by day and by any other useful dimension. Propose extra metrics that would help a
> sales manager, and I will choose which ones to include.
>
> Constraints: build on Odoo's native POS analysis where possible; net out refunds;
> show sales without a salesperson as their own group; count completed sales only by
> default; respect multi-company access.

### P18 — Extras chosen

> Include two of the proposed extras:
> 1. **Commission rate** per salesperson, applied to sales without tax. A rate change
>    must not rewrite past commissions.
> 2. **Order count and average order value** per salesperson.
>
> Leave out the PDF statement and the smart button.

---

## 3. Release

### P19 — Handover explanation

> Explain everything that was built in plain language: what each module does, where to
> find each feature in the menus, and how to set it up. One example question: where do
> I set the commission rate?

### P20 — Compliance check

> Check the repository against the assessment PDF, item by item: features, README
> sections, installation, configuration, testing strategy, demo data, the GenAI log and
> the question about conflicts between the two POS modules. List anything missing
> before we submit.

### P21 — Publish

> Push the repository to the public GitHub repository I created
> (`ziadelawdy/odoo-dev-assessment`). Confirm the remote matches the local `main` and
> that the README opens without signing in.

### P22 — Prompt documentation

> Add the prompts I used to `docs/`, in English, rewritten as clean, professional
> prompts that keep their original meaning. Link them from the README and the prompt
> log.
