# GenAI usage log

**Tool:** Claude Code (Anthropic), model Claude Opus 5.5, running against the local
Odoo 20.0 Enterprise source. The conversation was in Egyptian Arabic; prompts below are
faithful English summaries, in order. Outputs are summarised, with links to the artefacts
they produced.

The workflow was set up so the AI could not "vibe" its way past correctness. It worked as
brainstorm → written design → reviewed plan → test-first implementation → independent
review. Every framework claim was verified against the installed Odoo 20 source before it
was used.

## Exercise 2 — Dynamic Trial Balance

| # | Prompt (summary) | Output / outcome |
|---|---|---|
| 1 | "Study the assessment PDF and list everything: requirements, gaps, problems. Tell me exactly what is required before we start." | Full requirement breakdown of the three exercises, plus the spec gaps. Examples: missing `date_from`/`date_to`; journals and analytic described as Many2one but meaning several; the missing mockup; P&L opening balances across fiscal years; the XSS risk of HTML receipt fields; `XmlReceipt` not existing in recent POS. |
| 2 | "Exercises 2 + 3. Target the installed Odoo 20 (not 18). New repo." | Repo scaffolded. A separate dev config (port, DB) so the user's running Odoo services and databases were never touched. |
| 3 | A "master development protocol": use real skills, Analyze → Plan → Implement → Test → Debug → Review → Verify, no unverified claims, final status report. | Adopted as the working method for the whole project. Context7 was not available, so the installed Odoo 20 source was the primary reference. |
| 4 | "What would make a reviewer say the developer understands Odoo accounting?" (answered by the user with criteria: per-account parity with native TB, correct opening vs movement, fiscal-year boundary, posted/draft, multi-company, tests as proof). | Became the success criteria and the test strategy (parity tests account by account). |
| 5 | AI read the native `account_trial_balance_report.py`, `account_report.py` and the analytic report. | Findings: `account.group` is gone in Odoo 20 (hierarchy uses `account.account.parent_id`). The native TB has a single Balance column for Initial/End. Journals are disabled on the TB. The analytic shadow table gives proportional amounts. Decision proposed: build on the native engine through an inherited handler. |
| 6 | "Initial/End Debit-Credit like the classic trial balance." / "Analytic: show only the 60 % share." | Recorded in the design ([spec](superpowers/specs/2026-11-08-dynamic-trial-balance-design.md)). |
| 7 | Independent "builder" review of the design by a second AI agent. | Raised 4 questions. Two were settled as documented calls. Two went to the user: Preview filter editing → read-only summary, re-open the wizard; analytic → accounts disappear, plus a "not balanced" notice. |
| 8 | "Approved — write the plan." | [Implementation plan](superpowers/plans/2026-11-08-dynamic-trial-balance.md): 8 test-first tasks. While planning, the grand-total rule was corrected: a net-split total would always read 0 / 0. |
| 9 | "Execute everything; one independent review at the end." | Implemented task by task with RED → GREEN evidence. Findings during implementation, each verified in the source: |
|   |   | • The native TB postprocessor double counts End once Initial has 3 columns, so End is recomputed as Initial + Movement. |
|   |   | • The total line is identified by its `total` markup, not by position. |
|   |   | • Odoo 20 replaced `ir.model.access` with `ir.access` (new CSV format). |
|   |   | • The native XLSX has no header, so a handler hook writes one and the native writer renders the table below it. |
|   |   | • The hierarchy option is only available when parent accounts exist. |

## Exercise 3 — POS Enhancements

| # | Prompt (summary) | Output / outcome |
|---|---|---|
| 1 | "Start Exercise 3." The user explained, in their own words, how a new line should inherit the order salesperson. | Assignment rules agreed: global sets order and lines; a line action sets one line; new lines inherit; a line changed manually keeps its value; global again overwrites. |
| 2 | A receipt mockup (original vs enhanced) was shown inline, and the user approved it. | Enhanced layout fixed: logo, company, customer, then a Product/Qty/Price/Total table with the salesperson under the product. |
| 3 | An AI subagent mapped the Odoo 20 POS extension points. | Findings: OWL 3 (`useProps`); `pos.load.mixin`; native serializer for sync; the receipt is server QWeb rendered client-side plus a Python mirror; `SelectionPopup` with `makeAwaitable`. |
| 4 | A builder check on the design by a second agent. | Header blocks are replaced, not duplicated. Feature-off data policy. Basic receipt columns. The test cases are copied verbatim. |
| 5 | Test-first implementation (6 tasks). | Findings: two order-line list views (both extended); the tours were *skipped* until `websocket-client` was installed (user approved, isolated folder); combo children did not inherit the order salesperson, caught by a tour and fixed; the receipt CSS belongs in the receipt style template; integration tests were proven by deliberate mutations (both caught). |
| 6 | Manual test by the user: "I can't find where to set a salesperson per product. When I add the first product, ask me who the salesperson is and use them for all following products, but let me change all or one by one." | Root cause: the line icon used Font Awesome, which the Odoo 20 POS does not load, so the button rendered empty (tours clicked it anyway). It was replaced by a labelled pill with the POS `oi` icon. A first-product prompt was added; its choice becomes the order salesperson. Test-first: two new tours failed (no popup), then passed; four existing tours now skip the prompt explicitly. |
| 7 | Second round of user feedback after manual testing: show the receipt while paying, print and email it automatically, and make the receipt cleaner and more modern. | Brainstorm with three mockups; the user picked design A and chose to keep the products table (assessment compliance) over two-line items. Design, then a builder check, then the plan. Test-first, four tasks: the prompt asks again after a dismissed popup; a live preview in its own iframe; auto email through the native `action_send_receipt`; the design A layout and the placeholder logo hidden. Auto print reuses native `iface_print_auto`. Every test was seen failing first; auto email was also proven by a deliberate mutation. |
| 8 | Independent whole-branch review (opus). | No critical issues. Fixed test-first: the first-product prompt no longer re-credits refund lines; it does not ask for lines added by code (discount, tips, sale-order import); the preview keeps its scroll position. The combined run found that the enhanced receipt CSS named the salesperson module's class, which is coupling and broke the salesperson tests; it now styles the product cell generically. |
