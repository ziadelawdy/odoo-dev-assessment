# Salesperson Sales Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** POS reports per salesperson: what they sold (products, days), commission, orders and average order value.
**Architecture:** extend the native `report.pos.order` SQL view with the line salesperson and a commission column; add a second SQL view at (order, salesperson) grain for order counts and average order value.
**Tech Stack:** Odoo 20 (`odoo.tools.SQL`, `ir.access`), pivot/graph/list views.
**Spec:** `docs/superpowers/specs/2026-11-10-salesperson-sales-report-design.md`

## Global Constraints

- Odoo 20 only: `ir.access` CSV, `SQL()` composition, no `ir.rule` / `ir.model.access`.
- Amounts reuse the native report expressions (currency rate, sign of refunds).
- Tests: `post_install`, `-at_install`, in `azk_pos_salesperson/tests/test_salesperson_report.py`, using `AzkPosSalespersonCommon._sync_order`.

## Review Focus

1. Refund lines (negative qty) must reduce sales and commission.
2. Orders with lines from two salespersons: each salesperson counts the order once, with only their own lines.
3. Rate changed after a sale: past commission unchanged.
4. Lines without salesperson: present in both reports, grouped as empty.
5. Multi-company: the new view has a company rule like the native one.

---

### Task 1: Commission rate frozen on the line

**Files:** `models/pos_sale_person.py`, `models/pos_order_line.py`, `views/pos_sale_person_views.xml`, test file.

- [ ] Tests: `test_commission_rate_bounds` (rate 150 → ValidationError, -1 → ValidationError); `test_line_freezes_commission_rate` (A rate 10, sync line with A → line rate 10; set A rate 20 → line still 10; new sale → 20).
- [ ] RED, then add `commission_rate = fields.Float('Commission (%)', digits=(5, 2))` + `@api.constrains` 0..100; `azk_commission_rate = fields.Float(compute, store=True, depends('salesperson_id'))` on the line; field in salesperson list/form.
- [ ] GREEN, commit.

### Task 2: Salesperson and commission on `report.pos.order`

**Files:** `report/__init__.py`, `report/pos_order_report.py`, test file.

- [ ] Tests: `test_report_lines_carry_salesperson` (rows by product → salesperson matches the line); `test_report_sums_by_salesperson` (read_group by salesperson: `price_subtotal_excl` equals sum of `price_subtotal` of that salesperson's lines; unassigned group present); `test_report_commission` (10 % of untaxed; refund line negative commission); `test_report_order_count_distinct` (order with 2 lines of A counts 1 order for A).
- [ ] RED, then extend `_select` with `l.salesperson_id AS salesperson_id` and the commission expression (native untaxed expression × `COALESCE(l.azk_commission_rate, 0) / 100`, rounded to currency decimals).
- [ ] GREEN, commit.

### Task 3: Performance view (order × salesperson)

**Files:** `report/salesperson_performance_report.py`, `security/ir.access.csv`, test file.

- [ ] Tests: `test_performance_one_row_per_order_and_salesperson` (order with A and B lines → 2 rows); `test_performance_average_order_value` (A sells 30 then 10 untaxed in two orders → orders 2, sales 40, average 20); `test_performance_company_rule` (rows of another company invisible); `test_performance_refund_negative`.
- [ ] RED, then `azk.pos.salesperson.report` (`_auto = False`), grouped SQL over `pos_order_line`/`pos_order`, fields: date, order_id, salesperson_id, config_id, session_id, partner_id, company_id, currency_id, state, amount_untaxed (sum), amount_total (sum), average_order_value (same value, `aggregator='avg'`), product_qty, line_count, commission. `ir.access`: read for `point_of_sale.group_pos_user`, global company line.
- [ ] GREEN, commit.

### Task 4: Menus, views, filters

**Files:** `views/salesperson_report_views.xml`, manifest, test file.

- [ ] Test: `test_report_actions_and_menus` (both actions exist, open pivot first, menus under `point_of_sale.menu_point_rep` for managers; native search view has the salesperson group-by).
- [ ] RED, then views (pivot/graph/list/search for both models), actions with default filter `completed`, menus, inherit native search view.
- [ ] GREEN; full POS suite (both modules) green; browser check on the demo DB; README + prompt log; commit.

### Final: independent review, fix pass, merge decision.
