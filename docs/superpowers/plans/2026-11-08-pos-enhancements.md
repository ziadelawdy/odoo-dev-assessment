# POS Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two independent Odoo 20 POS addons, `azk_pos_salesperson` and `azk_pos_enhanced_receipt`. Each works alone, and they compose when installed together.

**Architecture:**
- Backend: Python models, plus `pos.load.mixin` for offline loading.
- Frontend: OWL 3 template extensions and `patch()` on native components, models and the receipt data generator.
- Receipt:
  - server QWeb `<template inherit_id>` on `point_of_sale/receipt/pos_order_receipt.xml`;
  - the same arch renders on the client and the server;
  - the data comes from `generate_printer_data.js`, mirrored by `pos.order.receipt` in Python.

**Tech Stack:**
- Odoo 20.0+e (`point_of_sale`, `hr`), OWL 3 (`useProps`, `signal`), QWeb.
- Tests: `odoo.tests` (`TransactionCase`, and `TestPointOfSaleHttpCommon` with tours driving Chrome at `C:\Program Files\Google\Chrome\Application\chrome.exe`).

**Spec:** `docs/superpowers/specs/2026-11-08-pos-enhancements-design.md`

## Global Constraints

- Odoo `20.0+e-20261105`. Verify every API in `C:\Program Files\Odoo 20.0e.20261105\server\odoo\addons` before use.
- Field names exactly as the spec says:
  - `active_salesperson_feature`, `allowed_sale_person_ids`, `use_customized_receipt`, `receipt_logo`, `company_name`, `company_details`, `show_customer_details` on `pos.config`;
  - `salesperson_id` on `pos.order.line` (and on `pos.order`, spec §6);
  - model `pos.sale.person` with `name`, `phone_number`, `employee_id` (+ `active`, `company_id`).
- `company_name` and `company_details` are `fields.Html` with the default sanitizer.
- No edits to native files. Only `inherit_id`, `t-inherit` (extension mode) and `patch()`.
- Security: `security/ir.access.csv` in the Odoo 20 format (`id,name,model_id,group_id/id,operation,domain`). `pos.sale.person` gets `r` for `point_of_sale.group_pos_user` and `crud` for `point_of_sale.group_pos_manager`.
- Popup: native `SelectionPopup` via `makeAwaitable(this.dialog, SelectionPopup, {title, list})`. First entry "No salesperson" clears the value.
- Assignment rules (spec §5.1):
  - global sets the order salesperson and every line;
  - a line action sets that line only;
  - new lines take the order salesperson;
  - global again overwrites all lines.
- Merge rule: a product only merges into an existing line with the same `salesperson_id`.
- Receipt rules (spec §5.2 and "Settled after the builder check"). Enhanced mode:
  - replaces the native logo (falls back when `receipt_logo` is empty), `partner_info` and the footer `company_info_receipt`;
  - customer block only when `show_customer_details`;
  - table columns are Product | Qty | Price | Total, or Product | Qty on the basic receipt.
- Tests run on a **new** database `azk_pos_test`. Never touch `noktest`, `nokasse`, `odoo20_dev`, `azk_tb_test` or `azk_tb_demo`.
- Stop the dev server on 8075 before running tours, because the tours need the HTTP port.

**Test command** (from `C:\Users\ziad.elawdy\odoo-assessment`, PowerShell; tours need HTTP, so no `--no-http`):

```
& "C:\Program Files\Odoo 20.0e.20261105\python\python.exe" "C:\Program Files\Odoo 20.0e.20261105\server\odoo-bin" -c odoo-dev.conf -d azk_pos_test -i <modules> --test-tags <tags> --stop-after-init --log-level=test
```

- `<modules>` is `azk_pos_salesperson`, `azk_pos_enhanced_receipt`, or both comma-separated.
- `<tags>` is e.g. `/azk_pos_salesperson`, or `/azk_pos_salesperson:TestClass.test_name`.
- Use `-u` once the module is installed.
- Pass = `0 failed, 0 error(s)` in the result line.

## Review Focus

1. **Adding a product that already has a line with a different salesperson** (click, barcode, or + quantity). Expected: a new line is created; the other salesperson's line is not changed. *(Task 3 tour `AzkSalespersonMergeTour`.)*
2. **Refreshing the browser while a draft order has salespersons assigned.** Expected: the order salesperson and the line salespersons are still there after the reload, and new lines still inherit. *(Task 3 tour `AzkSalespersonReloadTour`.)*
3. **Combo products.** Expected: assigning a salesperson to a combo parent line (or globally) also sets its child lines, so the receipt and backend stay consistent. *(Task 3 tour step in `AzkSalespersonGlobalTour` plus Python assertion.)*
4. **Script or event-handler HTML typed into company name/details.** Expected: stripped on save, never executed on the receipt or in the backend. *(Task 4 `test_company_html_sanitized`.)*
5. **Enhanced receipt enabled with no `receipt_logo` uploaded.** Expected: the native company logo prints, not an empty image. *(Task 5 `test_enhanced_logo_fallback`.)*

---

## File Structure

```
azk_pos_salesperson/
├── __init__.py, __manifest__.py              # depends: point_of_sale, hr
├── models/{__init__,pos_sale_person,pos_config,res_config_settings,pos_order,pos_order_line,pos_session}.py
├── receipt/{__init__.py,pos_order_receipt.py,pos_order_receipt.xml}   # Python mirror + template
├── views/{pos_sale_person_views,pos_config_views,res_config_settings_views,pos_order_views}.xml
├── security/ir.access.csv
├── demo/pos_sale_person_demo.xml             # Salesperson A, B, C
├── static/src/app/models/{pos_order,pos_order_line}.js
├── static/src/app/components/orderline/orderline.{js,xml}
├── static/src/app/screens/product_screen/control_buttons/control_buttons.{js,xml}
├── static/src/app/utils/salesperson_popup.js # selectSalesperson(pos, dialog, current)
├── static/src/app/utils/printer/generate_printer_data.js
├── static/src/css/salesperson.scss          # optional styling
├── static/tests/tours/salesperson_tours.js
└── tests/{__init__,common,test_salesperson_backend,test_salesperson_receipt,test_salesperson_ui}.py

azk_pos_enhanced_receipt/
├── __init__.py, __manifest__.py              # depends: point_of_sale
├── models/{__init__,pos_config,res_config_settings}.py
├── receipt/{__init__.py,pos_order_receipt.py,pos_order_receipt.xml}
├── views/{pos_config_views,res_config_settings_views}.xml
├── static/src/app/utils/printer/generate_printer_data.js
├── static/src/css/enhanced_receipt.scss
├── static/tests/tours/enhanced_receipt_tours.js
└── tests/{__init__,common,test_enhanced_backend,test_enhanced_receipt,test_enhanced_ui}.py

tests_integration (inside azk_pos_enhanced_receipt/tests, skipped unless azk_pos_salesperson is installed):
└── test_both_modules.py
README.md (Exercise 3 section), docs/genai/prompt-log.md (Exercise 3 rows)
```

---

### Task 1: Salesperson backend (model, fields, loading, sync, views, settings, security)

**Files:** create the `azk_pos_salesperson` skeleton: models, views, security, demo, `tests/common.py`, `tests/test_salesperson_backend.py`.

**Interfaces:**
- Produces:
  - Model `pos.sale.person` (`_inherit = ['pos.load.mixin']`), with:
    - `_load_pos_data_domain(self, data)`: returns `[('id', 'in', config.allowed_sale_person_ids.ids)]` when `config.active_salesperson_feature`, else `[('id', '=', False)]`, where config = `self.env['pos.config'].browse(data['pos.config'][0]['id'])`. Mirror how `pos_hr/models/hr_employee.py:15` reads the config from `data`.
    - `_load_pos_data_fields(self, config)`: returns `['id', 'name', 'phone_number', 'employee_id']`.
  - `pos.session._load_pos_data_models(config)` gets `+ ['pos.sale.person']`.
  - `pos.order.line._load_pos_data_fields(config)` gets `+ ['salesperson_id']`.
  - `pos.order._load_pos_data_fields(config)` gets `+ ['salesperson_id']`, if `pos.order` uses an explicit list. Verify; otherwise nothing.
  - `res.config.settings`: `pos_active_salesperson_feature` and `pos_allowed_sale_person_ids`, both `related='pos_config_id.<field>'`, `readonly=False`.
  - Demo XML ids: `azk_pos_salesperson.sale_person_a|b|c`, named "Salesperson A/B/C".
  - Test base: `AzkPosSalespersonCommon(TestPoSCommon or the native common that provides a config, session and products)`. It exposes:
    - `cls.config` and `cls.sp_a`, `cls.sp_b`, `cls.sp_c`;
    - `_open_session()`;
    - `_sync_order(lines: list[dict], order_vals: dict) -> pos.order`, which builds the payload the way native POS tests call `sync_from_ui`. Find a native helper in `point_of_sale/tests/common.py` and reuse it.
- Menu: *Point of Sale › Configuration › Salespersons*. Parent: the POS configuration menu xml id (verify).

- [ ] **Step 1: Write failing tests** in `test_salesperson_backend.py`:
  - `test_name_required`: creating without `name` raises.
  - `test_load_only_allowed_when_active`:
    - Config with the feature on, allowed = A, B.
    - `session.load_data(['pos.sale.person'])` (or the native load entry point) returns exactly A and B.
    - With the feature off it returns nothing.
  - `test_order_line_load_fields`: `'salesperson_id' in env['pos.order.line']._load_pos_data_fields(config)`.
  - `test_sync_stores_salespersons`:
    - Sync one order with `salesperson_id` = A on the order, and lines X→A and Y→B.
    - The created `pos.order.salesperson_id` == A.
    - The lines' `salesperson_id` == A and B.
  - `test_sync_without_salesperson`: lines synced without the key have an empty `salesperson_id`.
  - `test_access_rights`:
    - A `group_pos_user` user can read `pos.sale.person` but `create` raises `AccessError`.
    - A `group_pos_manager` user can create.
  - `test_backend_views_show_salesperson`:
    - `env['pos.order.line'].get_views([(False, 'list')])` arch contains `salesperson_id`.
    - The `pos.config` form and `res.config.settings` form archs contain `active_salesperson_feature` and `allowed_sale_person_ids`.
- [ ] **Step 2: Run** the test command with `-i azk_pos_salesperson`. Expected: FAIL, because the module does not exist yet (or the model is missing).
- [ ] **Step 3: Implement** the files above. List/form/search views for `pos.sale.person`; search by name, phone, employee.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(pos-salesperson): model, loading, sync, views`.

### Task 2: Salesperson on the receipt (client + server)

**Files:**
- Create: `receipt/pos_order_receipt.py`, `receipt/pos_order_receipt.xml`, `static/src/app/utils/printer/generate_printer_data.js`.
- Test: `tests/test_salesperson_receipt.py`.

**Interfaces:**
- Produces:
  - Receipt line dict key `salesperson_name: str | False`, set on both sides:
    - JS: patch the generator's `generateLineData` and add `salesperson_name = line.salesperson_id?.name || false`.
    - Python: extend `pos.order.receipt._order_receipt_generate_line_data`. Verify its exact name at `point_of_sale/receipt/pos_order_receipt.py:129`.
  - Receipt `conditions['azk_salesperson']: bool` = `config.active_salesperson_feature`, in both generators.
  - Template: `inherit_id="point_of_sale.pos_orderline_receipt_information"` inserts `<div class="azk-salesperson">Salesperson: <t t-out="line['salesperson_name']"/></div>` inside `//div[@name='extra-info']`, guarded by `t-if="conditions.get('azk_salesperson') and line.get('salesperson_name')"`.
- Test helper `_render_receipt(order) -> str`. It renders `point_of_sale.pos_order_receipt` server-side with `order.order_receipt_generate_data()`, the same way `action_send_receipt` does (`point_of_sale/models/pos_order.py:1059`; verify the call).

- [ ] **Step 1: Write failing tests:**
  - `test_receipt_data_has_salesperson_name`: an order synced with X→A gives `lines[i]['salesperson_name'] == 'Salesperson A'`.
  - `test_receipt_prints_name_when_active`: the rendered HTML contains `Salesperson: Salesperson A`, and `Salesperson A` appears after `X`'s product name in the HTML.
  - `test_receipt_hides_name_when_feature_off`: the same order, after the config feature is turned off, renders without `azk-salesperson`.
  - `test_receipt_no_name_when_unassigned`: a line without a salesperson renders no `azk-salesperson` block.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Register the JS in `point_of_sale._assets_pos` in the manifest.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(pos-salesperson): salesperson on receipt`.

### Task 3: Salesperson POS UI (icon, button, popup, rules) with tours

**Files:**
- Create: the `static/src/app/**` JS/XML files listed in the File Structure, `static/tests/tours/salesperson_tours.js`.
- Test: `tests/test_salesperson_ui.py`.

**Interfaces:**
- Produces:
  - `selectSalesperson(pos, dialog, currentId) -> Promise<record|null|undefined>` in `utils/salesperson_popup.js`.
    - Opens `SelectionPopup` with list `[{id: 0, label: _t("No salesperson"), item: null}, ...pos.models['pos.sale.person'].getAll()]` and the current one `isSelected`.
    - Resolves to the record, to `null` for "No salesperson", or to `undefined` if closed.
  - `PosOrder` patch:
    - `setSalespersonOnAllLines(person|null)`: sets `this.salesperson_id` and every line, including combo children.
    - New lines take `this.salesperson_id`. Hook the native line creation/add path; verify which method `pos_store.addLineToOrder` calls.
  - `PosOrderline` patch:
    - `setSalesperson(person|null)` also sets combo children.
    - `canBeMergedWith(other)` additionally requires `this.salesperson_id?.id === other.salesperson_id?.id` (verify the native method name).
  - Orderline template extension (feature active only):
    - a button `.azk-salesperson-btn`, with icon `fa fa-user-plus`, `aria-label="Assign salesperson"`, and `ev.stopPropagation()`;
    - a span `.azk-salesperson-name` showing the line's salesperson name.
  - ControlButtons extension (feature active only): button `.azk-assign-order-salesperson` labelled "Assign Salesperson to Order", in the main bar next to the native buttons.
  - Tours, registered in `web.assets_tests`:
    - `AzkSalespersonLineTour`
    - `AzkSalespersonGlobalTour`
    - `AzkSalespersonNoneTour`
    - `AzkSalespersonInheritTour`
    - `AzkSalespersonMergeTour`
    - `AzkSalespersonReloadTour`
    - `AzkSalespersonHiddenTour`
  - Reuse the native helpers in `@point_of_sale/../tests/pos/tours/utils/*`.

- [ ] **Step 1: Write failing tour tests** in `test_salesperson_ui.py`. The class extends `TestPointOfSaleHttpCommon`. Each test runs `self.start_pos_tour(<name>)` on `self.main_pos_config` with the feature on and A, B, C allowed, then asserts the database state:
  - `test_tc2_line_assignment`. Tour: add X, line icon → A; add Y, line icon → B; pay; validate. DB: X line = A, Y line = B.
  - `test_tc3_global_overwrites`. Tour: C→A, D→B individually, then global → C; both lines show "Salesperson C"; pay. DB: both lines = C, order = C. The tour also adds a combo product before the global assignment. DB: the combo children = C.
  - `test_tc4_no_assignment`. Tour: add products, pay. DB: every `salesperson_id` is empty.
  - `test_inherit_after_global`. Tour: global A, add X (shows A); line icon on X → B; add Y (shows A); pay. DB: X = B, Y = A.
  - `test_merge_rule`. Tour:
    1. Global → A.
    2. Add X (line 1, A).
    3. Line 1 icon → B.
    4. Add X again. The order salesperson A differs from line 1 (B), so a new line 2 (A) is created.
    5. Add X a third time. It merges into line 2 (qty 2).

    DB: two X lines, one with B (qty 1) and one with A (qty 2).
  - `test_reload_keeps_assignment`. Tour: global A, line X → B, refresh the page (native tour reload step), check that X shows B and that a newly added Y shows A.
  - `test_hidden_when_feature_off`. Feature off. Tour asserts `.azk-salesperson-btn` and `.azk-assign-order-salesperson` are absent.
- [ ] **Step 2: Run** (stop any server on 8075 first). Expected: FAIL, because the tours are missing or the selectors are not found.
- [ ] **Step 3: Implement** the UI and the patches.
- [ ] **Step 4: Run** all `/azk_pos_salesperson` tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(pos-salesperson): POS assignment UI and tours`.

### Task 4: Enhanced receipt backend (fields, sanitizer, views, settings)

**Files:** create the `azk_pos_enhanced_receipt` skeleton (models, views), `tests/test_enhanced_backend.py`.

**Interfaces:**
- Produces:
  - `pos.config` fields per the Global Constraints. `receipt_logo = fields.Image(max_width=512, max_height=512)` (an Image is a Binary; it keeps the receipt light).
  - `res.config.settings`: `pos_use_customized_receipt`, `pos_receipt_logo`, `pos_company_name`, `pos_company_details`, `pos_show_customer_details`, all related and `readonly=False`. Verify there is no clash with existing `res.config.settings` names.
  - Views:
    - `pos.config` form: a "Receipt Layout" group; the dependent fields are `invisible="not use_customized_receipt"`.
    - Settings: a `<setting>` inside `pos_bills_and_receipts_section`.

- [ ] **Step 1: Write failing tests:**
  - `test_fields_exist_and_defaults`: all five fields exist on `pos.config`; the booleans default to False.
  - `test_company_html_sanitized`: writing `'<b>NOX</b><script>alert(1)</script><img src=x onerror=alert(1)>'` to `company_details` stores no `<script` and no `onerror`, and keeps `<b>NOX</b>`. The same check for `company_name`.
  - `test_views_expose_fields`: the `pos.config` form arch and the `res.config.settings` arch contain all five field names.
  - `test_no_native_field_clash`: none of the five names existed on `pos.config` before the module. Assert via `self.env['ir.model.fields']`: each field's `modules` (or `module` field; verify) includes `azk_pos_enhanced_receipt`.
- [ ] **Step 2: Run** with `-i azk_pos_enhanced_receipt`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(pos-receipt): receipt layout settings`.

### Task 5: Enhanced receipt rendering (client + server)

**Files:**
- Create: `receipt/pos_order_receipt.{py,xml}`, `static/src/app/utils/printer/generate_printer_data.js`, `static/src/css/enhanced_receipt.scss`.
- Test: `tests/test_enhanced_receipt.py`.

**Interfaces:**
- Produces, in both generators:
  - `conditions['azk_enhanced'] = config.use_customized_receipt`.
  - `conditions['azk_show_customer'] = config.show_customer_details`.
  - `extra_data['azk_company_name']` and `extra_data['azk_company_details']`: markup-safe HTML. JS `markup(...)`, Python `Markup(...)`. Both values are already sanitized on save.
  - `extra_data['azk_customer']`: `{name, address_lines: list[str]}`, or False.
  - `image['logo']`: overridden with the `receipt_logo` data URI when enhanced and the logo is set. JS: `imageDataUri(config.receipt_logo.content)`; Python: `image_data_uri(config.receipt_logo)`.
- Templates (all guarded by `conditions.get('azk_enhanced')`):
  - **Header** (`pos_order_receipt_header`): after the logo div, a `div.azk-company` with name and details. `partner_info` is replaced by `div.azk-customer`, shown only when `azk_show_customer`. When enhanced is off, the native header renders unchanged.
  - **Lines** (`pos_order_receipt`): the native `t-foreach="lines"` tables are replaced by one `table.azk-lines-table`.
    - Header row: Product, Qty, Price, Total. Price and Total only when not `conditions['basic_receipt']`.
    - Each row's Product cell `t-call`s `point_of_sale.pos_orderline_receipt_information`, with a `t-set="azk_table_mode" t-value="True"`.
  - **Information** (`pos_orderline_receipt_information`): the standard unit-price span gets `t-if` and `not azk_table_mode`. Use a `position="attributes"` extension that keeps the native condition.
  - **Footer** (`pos_order_receipt_footer`): the `company_info_receipt` call is hidden when enhanced.

- [ ] **Step 1: Write failing tests.** Render server-side via a `_render_receipt(order)` helper; the same approach as Task 2, duplicated in this module's `tests/common.py`.
  - `test_enhanced_on_renders_layout`:
    - Config with enhanced on, logo, company name `NOX Trading`, details `<b>12 Tahrir St</b>`, customer details on, and an order for a partner with a street.
    - HTML contains `azk-company`, `NOX Trading`, `<b>12 Tahrir St</b>` (not escaped), `azk-customer` with the partner name and street, `azk-lines-table`, header cells `Product`/`Qty`/`Price`/`Total`, and the logo `data:image` from `receipt_logo`.
  - `test_enhanced_off_is_native`: the same order with enhanced off. HTML contains none of `azk-company`, `azk-customer`, `azk-lines-table`, and does contain the native `name="standard-line"`.
  - `test_customer_hidden_when_flag_off`: enhanced on, customer details off. No `azk-customer`; the native `partner_info` block is absent too.
  - `test_enhanced_logo_fallback`: enhanced on, no `receipt_logo`. The logo `img` uses the native `config.logo` data.
  - `test_basic_receipt_table`: `order_receipt_generate_data(basic_receipt=True)`. The table has Product and Qty headers and no Price/Total headers.
  - `test_no_duplicate_company_info`: enhanced on. The footer has no `company_info_receipt` block, so the company name appears once.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Assets go in `point_of_sale._assets_pos`. The SCSS covers logo max-width, table borders, padding and right-aligned numbers.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(pos-receipt): enhanced receipt layout`.

### Task 6: Both modules together, assessment scenarios, docs

**Files:**
- Create: `azk_pos_enhanced_receipt/tests/test_both_modules.py`, `azk_pos_enhanced_receipt/tests/test_enhanced_ui.py`, `azk_pos_enhanced_receipt/static/tests/tours/enhanced_receipt_tours.js`.
- Modify: `README.md`, `docs/genai/prompt-log.md`.

**Interfaces:**
- Consumes: Tasks 1–5.
- `test_both_modules.py` skips (`unittest.SkipTest`) unless `azk_pos_salesperson` is installed. The test run installs both modules.
- Tours `AzkReceiptVisibilityTour` and `AzkConfigChangeTour` use the native receipt-screen helpers to assert on the rendered receipt DOM.

- [ ] **Step 1: Write failing tests:**
  - `test_salesperson_inside_enhanced_table`: both modules, enhanced and salesperson on, order X→A. The rendered HTML has `Salesperson: Salesperson A` inside `table.azk-lines-table`, exactly once.
  - `test_tc1_visibility_per_config`. Create the four configs of the spec table (names verbatim). For each one, run `AzkReceiptVisibilityTour` with expectations passed in the tour arguments (or one tour per config):
    - `.azk-salesperson-btn` present iff the salesperson feature is on;
    - `.azk-lines-table` present on the receipt iff enhanced;
    - the salesperson name shows on the receipt iff the feature is on and a line is assigned.
  - `test_tc5_config_change_needs_reload`. On `POS_All_Disabled`, the tour opens the POS. The test then writes both features True to the config through a tour step or a server call, without a reload. The tour completes a sale and asserts the native receipt and no salesperson UI.
- [ ] **Step 2: Run** with `-i azk_pos_salesperson,azk_pos_enhanced_receipt --test-tags /azk_pos_salesperson,/azk_pos_enhanced_receipt`. Expected: FAIL.
- [ ] **Step 3: Implement** whatever the integration reveals: tours, plus any CSS/template fixes.
- [ ] **Step 4: Run** the full test command for both modules. Expected: PASS, `0 failed, 0 error(s)`.
- [ ] **Step 5: README Exercise 3 section:**
  - features;
  - install;
  - configuration (the four configs and how to set them);
  - manual test steps (test cases 1–5);
  - automated tests;
  - **"Conflicts when both modules are installed"** (spec §8 verbatim content);
  - design calls (spec §10);
  - the Odoo 20 vs 18 note.
  Then add the Exercise 3 rows to `docs/genai/prompt-log.md`.
- [ ] **Step 6: Commit** `feat(pos): integration tests, assessment scenarios, docs`.
