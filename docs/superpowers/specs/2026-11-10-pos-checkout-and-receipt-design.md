# POS checkout flow and modern receipt: design

Date: 2026-11-10. Target: Odoo 20.0e (installed). Builds on the existing modules
`azk_pos_salesperson` and `azk_pos_enhanced_receipt` and on branch
`pos-first-product-prompt` (commit `56efae8`).

## Intent

The user tried the POS in a browser, with no receipt printer, and asked for a
smoother checkout and a better receipt:

1. Salesperson: when the first product is added, ask who the salesperson is.
   The following products take the same person, and the user can change all
   lines at once or one line at a time.
2. Payment screen: split the screen so the receipt is visible while paying.
   On Validate, print by itself, and if a customer is selected, email the
   receipt by itself.
3. Receipt: the current one looks crowded. The user wants clear sections, a
   clean modern look, and nothing running into anything else. Of three mockups
   the user picked **A**, the minimal one with dashed separators.

The user is not technical and is testing in the browser only. Success means
that a cashier can sell, pay and get a receipt without extra clicks, and that
the receipt reads at a glance.

## Already done (branch `pos-first-product-prompt`)

- The line button was invisible because the POS does not load Font Awesome. It
  is now a labelled pill (`oi` icon plus the name, or "Add salesperson").
- Adding the first product of an order opens the salesperson popup. The choice
  becomes the order salesperson and the next products inherit it.
- "Assign Salesperson to Order" (all lines) and the per-line pill (one line)
  already exist.

### One change to that behaviour (user-confirmed)

- **Popup closed without a choice:** the product is added unassigned, and the
  popup **asks again** for the next new product of the same order.
- **"No salesperson" chosen explicitly:** the order is unassigned on purpose,
  so stop asking for that order.
- **The order gets a salesperson by any route** (popup, order button, line
  pill): stop asking.

The "stop asking" state is client-only, per order, and does not need to
survive a reload. The current code checks `!order.lines.length`, so it never
asks again. It must track instead whether the question was answered for this
order.

## Goals

### G1. Live receipt preview on the payment screen

- **Layout.** On non-small screens the payment screen gets a third column on
  the right showing the receipt as it will print. The existing left column
  (methods, numpad, back and validate) and the centre column (amount due,
  payment lines) stay as they are, only narrower.
- **Small screens.** No preview, layout unchanged.
- **Same template as printing.** The preview renders
  `point_of_sale.pos_order_receipt` with the same data the printer gets
  (`ticketPrinter.getOrderReceiptData(order)`) in its own iframe. It must not
  use `#receipt-iframe-container`, which printing uses.
- **Live updates.** The preview re-renders, debounced, when the order changes:
  payment lines and amounts, customer, lines.
- **Draft label.** The order is still a draft at this point, so the native
  header would print "Pro forma receipt". The preview must hide that label.
  Printing after Validate is unaffected.
- **Setting.** A new boolean `azk_payment_receipt_preview` on `pos.config`
  (label "Receipt preview on payment screen", default True), shown next to the
  module's other receipt settings. Off means the native payment screen.
- **Module.** Belongs to `azk_pos_enhanced_receipt`. It works whether or not
  the customized receipt is on, and shows whichever receipt the POS would
  print.

### G2. Automatic printing on Validate

- **Reuse the native setting.** Odoo already has `iface_print_auto`
  ("Automatic Receipt Printing"). With no receipt printer it opens the
  browser's print dialog by itself after Validate
  (`printWithFallback`, then `printWeb`, then `window.print()`). No new code
  for printing.
- **Visibility.** The module surfaces the native field next to its own
  settings so it is easy to find. A `related` field or a view reference is
  fine, but not a duplicate field.
- **Demo.** The demo POS (Furniture Shop on `azk_tb_demo`) gets it switched on.
- **Limit (README).** Silent printing needs a real receipt printer (IoT, ePOS
  or a network printer). A browser cannot print without its dialog.

### G3. Automatic email on Validate

- **Setting.** A new boolean `azk_auto_email_receipt` on `pos.config` (label
  "Email receipt automatically", default False), next to the other settings.
- **When it sends.** The order is validated and synced to the server (it has a
  server id), the order has a customer, and the customer has a valid email.
  Then the POS calls the native `pos.order.action_send_receipt(email)`,
  exactly what the native "Send receipt" popup calls.
- **Does not block the cashier.** The call is fire-and-forget after
  validation. The cashier moves on to the next screen immediately.
- **Feedback.** On success, a short notification says the receipt was sent to
  the address. On failure (offline, server error), a warning notification
  appears and the sale is unaffected.
- **Offline.** The order is not synced yet, so nothing is sent and no retry
  queue is built. The cashier can still use the native "Send receipt" button
  later.
- **Out of scope.** No outgoing mail server is configured on the demo DB, so
  mails will end in "exception" state. That is accepted. Configuring the
  server is a later step for the user.

### G4. Receipt redesign: option A (customized receipt only)

Applies only when `use_customized_receipt` is on. The native receipt is
unchanged. The look is a narrow thermal ticket, top to bottom:

1. **Logo.**
   - `receipt_logo` if set.
   - Otherwise the company logo, but only if it is not Odoo's default
     placeholder (`res.company.uses_default_logo`).
   - Otherwise no logo at all. Today the "Your logo" placeholder prints.
2. **Company block,** centred: company name (larger, bold), details (small,
   muted), tax ID (small).
3. Dashed separator.
4. **Order block,** small, two columns per row: ticket number and
   date/time, cashier and customer name. When customer details are on, the
   customer address follows in small muted lines.
5. Dashed separator.
6. **Items, a table (user decision 2026-11-10).** The assessment requires a
   "clear table", and the user chose to stay compliant. So the existing
   Product | Qty | Price | Total table stays, restyled in the spirit of
   design A:
   - Light header row with a solid rule under it.
   - Dashed rules between items, no other borders.
   - Product names at the normal size and bold, so they do not wrap as they
     did before.
   - Numbers right-aligned in fixed, narrow columns.
   - The salesperson sits on its own small muted line under the product name,
     inside the Product cell, through the existing `extra-info` hook. Our
     call, from the builder check: no new coupling between the modules.
   - Discount and customer note: small muted lines in the Product cell.
   - Combo children: indented, without a price.
   - Basic receipt (prices hidden): Product | Qty only, as now.
7. Dashed separator.
8. **Totals.** Taxes (muted), Total (large, bold), payment method lines
   (muted), Change if any.
9. Dashed separator and the native footer content: footer text, "Powered by".
10. **Typography.** Product names must not render at the native `text-large`
    size that made them wrap in the current version. Use the normal size,
    bold. The receipt must fit the 80 mm / ~300 px width.

**Both renderers.** The client QWeb render and the Python mirror
(`pos.order.receipt`, used for email and download) produce the same layout, as
now.

**Combined with the salesperson module.** The salesperson tag must still come
through the existing named hook (`div[@name='extra-info']` in
`pos_orderline_receipt_information`). No bridge module.

## Non-goals

- Configuring an outgoing mail server.
- Silent printing in the browser.
- Changing the native (non-customized) receipt layout, apart from the
  salesperson line it already shows.
- Changes to the Trial Balance module.

## Anti-goals

These count as failures even if things technically work:

- The cashier waits for email or preview rendering before moving on.
- The preview and the printed receipt differ.
- Printing or the receipt breaks when either POS module is installed without
  the other.
- Any change to the do-not-touch databases (`noktest`, `nokasse`,
  `odoo20_dev`).

## Constraints

- Verify every API against the installed Odoo 20 source.
  - `PaymentScreen` template: `point_of_sale.PaymentScreen`, with
    `left-content`, `center-content` and an `ui.isSmall` branch.
  - `OrderPaymentValidation.afterOrderValidation` in
    `point_of_sale/static/src/app/utils/order_payment_validation.js`.
  - `PosTicketPrinter.getOrderReceiptData` and `generateIframe`.
  - Native receipt templates: `point_of_sale/receipt/pos_order_receipt.xml`.
- Workflow: test-driven, the existing test bases (`TestPoSCommon`,
  `TestPointOfSaleHttpCommon`, tours), and the existing 45 POS tests must stay
  green.
- Security: no credentials in code or logs.

## Decisions left to the builder

- The exact debounce and how the preview subscribes to order changes.
- The CSS of design A, within the layout above.
- Whether the preview iframe scales the receipt to fit the column.
- The notification wording.
- How tours assert the preview: an iframe that contains the order's product
  names and the amount, for example.

## Calls made by the designer (from the builder check)

- **Table, not two-line blocks.** The products stay in a table, restyled in
  the spirit of design A. This was the user's decision: stay compliant with
  the assessment.
- **Salesperson line.** In the Product cell, the salesperson goes on its own
  muted line through the native `extra-info` hook. It does not sit beside the
  qty.
- **Demo setup.**
  - Automatic printing (`iface_print_auto`) and automatic email are switched
    on for the Furniture Shop in `azk_tb_demo` with a one-off write. This is
    not module demo data, so test databases and headless tours never open a
    print dialog.
  - Tests that cover G2 and G3 set the flags themselves, and stub
    `window.print` or the RPC where needed.
