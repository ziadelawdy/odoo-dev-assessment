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

Pending (next milestone).
