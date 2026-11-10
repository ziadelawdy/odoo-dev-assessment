# POS checkout flow and modern receipt: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal.** A smoother checkout and a cleaner receipt. It covers four things:

- the salesperson prompt asks again after a dismissed popup;
- a live receipt preview on the payment screen;
- an automatic receipt email;
- design A styling of the customized receipt.

**Architecture.**

- The salesperson change is a small edit to the `PosStore.addLineToOrder`
  patch in `azk_pos_salesperson`.
- Everything else lives in `azk_pos_enhanced_receipt`:
  - an OWL component, `AzkReceiptPreview`, rendered by a `PaymentScreen`
    template extension;
  - a patch of `OrderPaymentValidation.afterOrderValidation` that sends the
    email;
  - two `pos.config` booleans plus one computed boolean;
  - QWeb template and style changes, mirrored in Python and JS as today.

**Tech stack.** Odoo 20.0e, OWL 3, QWeb, Python tests
(`TestPoSCommon`, `TestPointOfSaleHttpCommon`), and POS tours.

**Spec.** `docs/superpowers/specs/2026-11-10-pos-checkout-and-receipt-design.md`

**Base branch.** `pos-first-product-prompt` (commit `56efae8`). Work
continues on that branch.

## Global constraints

- Verify every Odoo API against the installed source in
  `C:\Program Files\Odoo 20.0e.20261105\server\odoo\addons`.
- Never touch the `noktest`, `nokasse` or `odoo20_dev` databases. Test
  databases are `azk_pos_test`; the demo database is `azk_tb_demo`.
- How to run the tests:
  - `python odoo-bin -c odoo-dev.conf -d azk_pos_test -u <module> --test-tags /<module> --stop-after-init`
  - Prefix the command with `MSYS_NO_PATHCONV=1` in Git Bash, and add
    `PYTHONPATH=<repo>\.local\pylibs` for tours.
  - Stop the 8075 demo server before running tours.
  - The test process may hang after it prints its result line: read the
    result, then kill it.
- Both modules must keep working installed alone and installed together.
- All 45 existing POS tests stay green. The tours from `56efae8` are part of
  that baseline.
- The cashier is never blocked by the email call or by the preview render.

## Review focus

Inputs the spec implies but no happy-path test covers:

1. **Customer without an email, or an invalid one,** with auto email on. No
   RPC and no notification. Pinned in Task 3.
2. **Order validated offline (not synced),** with auto email on. No RPC and
   no error dialog. Pinned in Task 3.
3. **Preview when the customized receipt is off.** It shows the native
   receipt, without the "Pro forma receipt" label. Pinned in Task 2.
4. **Company still on Odoo's placeholder logo, no `receipt_logo`.** No logo
   prints. A real logo still prints. Pinned in Task 4.
5. **Salesperson popup dismissed twice, then a choice is made.** The choice
   applies to all existing lines. Pinned in Task 1.

---

### Task 1: Salesperson prompt asks again after a dismissed popup

**Files:**
- Modify: `azk_pos_salesperson/static/src/app/services/pos_store.js`
  (`azkShouldAskSalesperson`, `addLineToOrder`).
- Test: `azk_pos_salesperson/static/tests/tours/salesperson_tours.js`
  (new tour `AzkSalespersonFirstProductDismissTour`).
- Test: `azk_pos_salesperson/tests/test_salesperson_ui.py` (new test that
  runs the tour).

**Interfaces:**
- `selectSalesperson` returns `undefined` when the popup is closed, `null`
  for "No salesperson", and a record when a person is chosen.
- The produced flag is `order.uiState.azkSalespersonAnswered`, a client-only
  boolean.

- [ ] **Step 1: Write the failing tour**

  1. Open the POS and click "Whiteboard Pen".
  2. Close the popup: Escape key, or the modal close button
     `.modal .btn-close`.
  3. Check the line shows "Add salesperson".
  4. Click "Letter Tray". The popup opens again (trigger
     `.modal .selection-item`). Close it again.
  5. Click "Desk Pad" and choose "Salesperson A".
  6. Check all three lines show "Salesperson A" (`lineShows` for each) and the
     order button shows "Salesperson A".
  7. Pay and end the tour.

  Add `test_first_product_dismiss_asks_again` to `test_salesperson_ui.py`,
  following the existing `start_pos_tour` tests.

- [ ] **Step 2: Run it and confirm it fails.** Expected failure: the tour
  times out at step 4, because no popup opens for the second product.

- [ ] **Step 3: Implement**

  `azkShouldAskSalesperson(vals, order)`:
  - Replace the `!order.lines.length` check with
    `!order.uiState?.azkSalespersonAnswered`.
  - Keep every other condition as is.

  `addLineToOrder`:
  - If `chosen !== undefined`, set `order.uiState.azkSalespersonAnswered = true`.
  - If `chosen` is truthy, also call `setSalespersonOnAllLines(chosen)`.
  - Then do the line add.
  - Line order matters. The prompt runs before `super`, so with an earlier
    dismissed line, `setSalespersonOnAllLines` must still cover that line.
    It already iterates `order.lines`, so it does.

  The `!order.salesperson_id` condition already stops the prompt when the
  order button or another route set a salesperson.

- [ ] **Step 4: Run the whole `/azk_pos_salesperson` suite.** Expected: all
  pass, including `FirstProductTour` and `FirstProductSkipTour`.

- [ ] **Step 5: Commit**

  ```
  fix(pos-salesperson): ask again when the first-product popup is dismissed
  ```

### Task 2: Live receipt preview on the payment screen

**Files:**
- Modify: `azk_pos_enhanced_receipt/models/pos_config.py`
  - add `azk_payment_receipt_preview = fields.Boolean(string='Receipt Preview on Payment Screen', default=True)`.
- Modify: `azk_pos_enhanced_receipt/models/res_config_settings.py`
  - add the related field `pos_azk_payment_receipt_preview`.
- Modify: `azk_pos_enhanced_receipt/views/pos_config_views.xml`
  - add a setting block next to `azk_customized_receipt` in both views.
- Create: `azk_pos_enhanced_receipt/static/src/app/components/receipt_preview/receipt_preview.js`
- Create: `azk_pos_enhanced_receipt/static/src/app/components/receipt_preview/receipt_preview.xml`
- Create: `azk_pos_enhanced_receipt/static/src/app/screens/payment_screen/payment_screen.js`
  - register the component on `PaymentScreen.components`.
- Create: `azk_pos_enhanced_receipt/static/src/app/screens/payment_screen/payment_screen.xml`
  - extend `point_of_sale.PaymentScreen`.
- Create: `azk_pos_enhanced_receipt/static/src/app/screens/payment_screen/payment_screen.scss`
- Test: `azk_pos_enhanced_receipt/static/tests/tours/enhanced_receipt_tours.js`
  - new tours `AzkPaymentPreviewTour` and `AzkPaymentPreviewOffTour`.
- Test: new file `azk_pos_enhanced_receipt/tests/test_checkout.py`
  - class `TestCheckoutUi(TestPointOfSaleHttpCommon)`.
- Modify: `azk_pos_enhanced_receipt/tests/__init__.py`

**Interfaces:**
- `AzkReceiptPreview` takes one prop, `order: t.object()`.
- It renders, in its own `<iframe class="azk-receipt-preview-frame">` inside
  `<div class="azk-receipt-preview">`, the result of:

  ```js
  renderToElement(
      "point_of_sale.pos_order_receipt",
      this.pos.ticketPrinter.getOrderReceiptData(order),
  )
  ```

  - Set `data.conditions.azk_preview = true` before rendering.
- Template: add `t-if="not conditions.get('azk_preview')"` to the native
  `div[@name='pro_forma_receipt']` in `pos_order_receipt_header`, so the
  preview hides "Pro forma receipt". The flag only exists in the preview, so
  printing is unaffected. This goes in `receipt/pos_order_receipt.xml`.

- [ ] **Step 1: Write the failing tours**

  `AzkPaymentPreviewTour`:
  1. Open the POS, click "Whiteboard Pen", skip any popup, and pick
     "APartner Full".
  2. Click Pay.
  3. Assert `.payment-screen .azk-receipt-preview iframe` exists.
  4. A `run` step reads the iframe document and asserts:
     - it contains "Whiteboard Pen";
     - it contains the customer name;
     - it does not contain "Pro forma".
  5. Click Bank. Assert the iframe text now contains "Bank": the preview
     updated.
  6. Validate and end the tour.

  `AzkPaymentPreviewOffTour`: with the flag False, after Pay, assert
  `negate(".azk-receipt-preview")`.

  Python tests `test_payment_preview` and `test_payment_preview_off` set the
  flag on `main_pos_config` and run the tours, following
  `test_both_modules.TestBothModulesUi`.

- [ ] **Step 2: Run them and confirm they fail.** Expected failure: the
  trigger `.azk-receipt-preview` is never found.

- [ ] **Step 3: Implement the field, settings, component and template
  extension**

  Template extension (`point_of_sale.PaymentScreen`):
  - In the non-small branch, after `div.center-content`, add
    `<div t-if="pos.config.azk_payment_receipt_preview" class="azk-receipt-preview-col ...">`
    containing `<AzkReceiptPreview order="currentOrder"/>`.
  - Leave the small branch untouched.

  Component:
  - Re-render with `useEffect`, keyed on a cheap signature string:
    - line uuids, quantities and prices;
    - payment line uuids and amounts;
    - `partner_id?.id`;
    - `amount_total`.
  - Debounce the render by 150 ms.
  - Set the iframe `srcdoc` from `el.outerHTML`, as native `generateIframe`
    does, but on its own iframe.

  SCSS:
  - The preview column takes about 32 % width and scrolls on its own.
  - The iframe is white, with a border and the receipt's natural width.

- [ ] **Step 4: Run the tours and the full `/azk_pos_enhanced_receipt`
  suite.** Expected: all pass.

- [ ] **Step 5: Commit**

  ```
  feat(pos-receipt): live receipt preview on the payment screen
  ```

### Task 3: Automatic receipt email, and auto print surfaced

**Files:**
- Modify: `azk_pos_enhanced_receipt/models/pos_config.py`
  - add `azk_auto_email_receipt = fields.Boolean(string='Email Receipt Automatically')`.
- Modify: `azk_pos_enhanced_receipt/models/res_config_settings.py`
  - add the related field `pos_azk_auto_email_receipt`.
- Modify: `azk_pos_enhanced_receipt/views/pos_config_views.xml`
  - a setting for auto email;
  - help text pointing to the native "Automatic Receipt Printing" setting.
- Create: `azk_pos_enhanced_receipt/static/src/app/utils/order_payment_validation.js`
  - patch `OrderPaymentValidation.prototype`.
- Test: tours `AzkAutoEmailTour` and `AzkAutoEmailNoEmailTour`, plus Python
  tests in `test_checkout.py`.

**Interfaces:**
- Produces `azkAutoEmailReceipt()`, a method on the patched
  `OrderPaymentValidation`. It is fire-and-forget and returns a promise,
  for tests.
- It calls the native `pos.order.action_send_receipt(email)` through
  `this.pos.data.call("pos.order", "action_send_receipt", [[order.id], email])`.

- [ ] **Step 1: Write the failing tests**

  Tours:
  - `AzkAutoEmailTour`:
    1. Pick "APartner Full" (give it an email in the Python setup).
    2. Pay with Bank and validate.
    3. Wait for the feedback screen.
  - `AzkAutoEmailNoEmailTour`: same flow with a customer that has no
    email.

  Python checks:
  - `test_auto_email_sends`: after the tour, the synced order has
    `email == partner.email`, and `mail.mail` (`model='pos.order'`) has a
    record for that order. A failed state is fine, since tests have no mail
    server. `action_send_receipt` writes `email` and creates the mail.
  - `test_auto_email_off`: flag False, same tour, no `mail.mail` for the
    order.
  - `test_auto_email_no_email`: no `mail.mail`, and the tour passed with no
    error dialog.
  - Offline (not synced): unit-level check in the tour.
    - Monkeypatch `order.isSynced` to false through the `posmodel` hook
      before validate if practical.
    - Otherwise cover it with a code-level guard and name it in the review.

- [ ] **Step 2: Run them and confirm they fail.** Expected:
  `test_auto_email_sends` fails because no `mail.mail` exists.

- [ ] **Step 3: Implement the patch**

  `afterOrderValidation(...args)`:
  - Call `const res = await super.afterOrderValidation(...args)`.
  - If `this.pos.config.azk_auto_email_receipt`, call
    `this.azkAutoEmailReceipt()` without awaiting it.
  - Return `res`.

  `azkAutoEmailReceipt()` returns early unless all of these hold:
  - `order.partner_id?.email` passes `isValidEmail` from
    `@point_of_sale/utils` (or wherever `send_receipt_popup.js` imports it);
  - `order.isSynced`;
  - `typeof order.id === "number"`.

  Otherwise it calls the RPC, then:
  - on success: `notification.add(_t("Receipt sent to %s", email), {type: "success"})`;
  - on error: `catch` and `notification.add(_t("The receipt could not be emailed."), {type: "warning"})`.

  The notification service is `this.pos.notification`, or the env service
  if absent (verify in source).

- [ ] **Step 4: Run the suite.** Expected: all pass.

- [ ] **Step 5: Commit**

  ```
  feat(pos-receipt): email the receipt automatically after validation
  ```

### Task 4: Receipt redesign (design A styled table, logo placeholder)

**Files:**
- Modify: `azk_pos_enhanced_receipt/models/pos_config.py`
  - add `azk_logo_is_placeholder = fields.Boolean(compute='_compute_azk_logo_is_placeholder')`.
  - It is True when `not config.logo`, or when
    `config.logo.content == self.env['res.company']._get_logo().content`.
  - It is non-stored and loaded to the POS with the other `pos.config`
    fields. Verify that `pos.config` loads all fields, as `receipt_logo`
    does today.
- Modify: `azk_pos_enhanced_receipt/receipt/pos_order_receipt.py` and
  `static/src/app/utils/printer/generate_printer_data.js`.
  - When enhanced, there is no `receipt_logo` and the logo is the
    placeholder, set `image['logo'] = False`.
- Modify: `azk_pos_enhanced_receipt/receipt/pos_order_receipt.xml`:
  - header markup: dashed sections, an order block (ticket, date, cashier,
    customer);
  - table styles (normal-size bold product names, dashed row rules, fixed
    numeric columns, muted secondary lines);
  - dashed separators before the totals and before the footer.

  Only `conditions.get('azk_enhanced')` paths change.
- Test: `azk_pos_enhanced_receipt/tests/test_enhanced_receipt.py`.

- [ ] **Step 1: Write the failing tests**

  - `test_placeholder_logo_hidden`:
    - set `config.logo` to `BinaryBytes(env['res.company']._get_logo().content)`
      and `receipt_logo=False`;
    - render;
    - assert there is no `<img` inside `name="logo"`.
  - `test_real_logo_kept`: the existing NATIVE_LOGO still renders. This
    already holds as `test_enhanced_logo_fallback`; keep it.
  - `test_design_a_sections`: the rendered HTML contains
    - `class="azk-sep"` at least three times (dashed separators);
    - `class="azk-order-info"`;
    - `azk-lines-table`.

    The existing header assertions (Product, Qty, Price, Total) keep
    passing.
  - The existing `test_enhanced_off_is_native` must still pass: no
    `azk-sep` when off.

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement the field, data mirror, templates and styles.**
  - Product name: in table mode, override the native `text-large` class of
    `div[@name='product-name']`. Use the `azk_table_mode` CSS scope
    `.azk-lines-table .name { font-size: inherit; font-weight: bold; }`
    rather than changing the native template.
  - The salesperson line keeps coming from `extra-info`. Style it as muted
    and small through `.azk-lines-table .azk-salesperson`.

- [ ] **Step 4: Run both module suites.** Expected: all pass, including
  `test_both_modules`.

- [ ] **Step 5: Commit**

  ```
  feat(pos-receipt): design A layout for the customized receipt, hide placeholder logo
  ```

### Task 5: Full verification, review, demo

- [ ] **Step 1: Run both POS suites.**
  - `/azk_pos_salesperson,/azk_pos_enhanced_receipt` on `azk_pos_test`.
  - Also run with only `azk_pos_enhanced_receipt` installed (fresh DB
    `azk_pos_test_solo`) to confirm independence.
  - Expected: 0 failed, 0 errors.
- [ ] **Step 2: Independent review** of `git diff main...HEAD`. Use
  superpowers:requesting-code-review with the most capable model. Fix
  findings test-first.
- [ ] **Step 3: Demo DB.**
  - Upgrade both modules on `azk_tb_demo`.
  - One-off write on the Furniture Shop: `iface_print_auto=True`,
    `azk_auto_email_receipt=True`, `azk_payment_receipt_preview=True`.
  - Give a demo customer an email.
  - Restart the 8075 server.
- [ ] **Step 4: Browser check** in the built-in browser:
  - first-product prompt;
  - preview updates;
  - the print dialog opens after Validate;
  - the email notification;
  - the receipt looks like design A.
- [ ] **Step 5: README (Exercise 3 section) and the GenAI prompt log,**
  then commit.
