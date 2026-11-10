# Salesperson sales report — design

**Status:** approved in chat on 2026-11-10 (core report + commission + order count / average order value).
**Module:** `azk_pos_salesperson` (the report belongs to the salesperson feature).

## Why

The shop owner wants to see, for every salesperson, exactly what they sold: which products,
which days, how much, and what they earned. Today the salesperson is stored on every POS order
line, but no report shows it.

## Goals

1. **Sales by Salesperson** (*Point of Sale › Reporting*): one row per sold line, credited to the
   salesperson **of the line** (an order can have several salespersons).
   - Views: pivot (default; salesperson rows, drill down to product / day), graph, list (every sale:
     date, order, POS, product, qty, amounts, salesperson, commission).
   - Measures: Orders (distinct), quantity, sales without tax, total with tax, discount, margin,
     commission.
   - Filters: completed sales (default), today / date ranges, salesperson, product, category, POS,
     session, refunds. Group by salesperson, product, category, day / week / month, POS, customer,
     payment method.
2. **Commission:** a commission rate (%) per salesperson. Commission = rate × the line's sales
   without tax (after discount; refunds are negative, so they reduce it).
3. **Salesperson Performance** (*Point of Sale › Reporting*): one row per (order, salesperson).
   Measures: Orders (count), sales without tax, total with tax, **average order value**, items,
   commission. Group by salesperson and day / week / month.
4. The native *Orders* analysis can also be grouped and filtered by salesperson.

## Decisions (builder's calls)

- **Built on the native `report.pos.order`** (one row per order line), the same way `pos_hr` adds the
  employee: `_select` is extended with `l.salesperson_id`. Every amount comes from the native
  expressions, so the report matches the native POS analysis exactly.
- **Commission rate is frozen at sale time.** The rate is copied onto the order line
  (`azk_commission_rate`, stored compute depending only on `salesperson_id`). Changing a
  salesperson's rate later does not rewrite past commissions.
- **Commission basis** is the untaxed line amount (the native `price_subtotal_excl` expression,
  currency-converted like the rest of the report).
- **Average order value** is the salesperson's own share of each order: an order with lines from A
  and B counts as one order for A (A's lines only) and one for B. The pivot cannot divide two sums,
  so a second SQL view at (order, salesperson) grain carries the per-order amount twice: summed
  (Sales) and averaged (Average order value).
- **Unassigned sales** appear as their own group (salesperson empty), so missed assignments are
  visible.
- **Completed sales** = state `paid` or `done`. It is a default filter, not a hard domain, so drafts
  and cancellations can still be inspected.
- **Access:** same as the native analysis (POS users read, company rule). Menus are for POS
  managers. The reports work whether the feature is on or off (history stays visible).

## Non-goals

- PDF statement and a smart button on the salesperson form (not chosen).
- Commission payout / accounting entries.
