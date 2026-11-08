# POS Enhancements — Design

- **Date:** 2026-11-08
- **Modules:** `azk_pos_salesperson`, `azk_pos_enhanced_receipt` (two independent addons, as the assessment requires)
- **Target:** Odoo 20.0 Enterprise (`20.0+e-20261105`). The assessment text targets Odoo 18 and the user chose 20; see the deviation notes below.
- **Source requirement:** "Odoo Dev Assessments.pdf", Exercise 3 (sections 1–6, test cases 1–5)

## 1. Intent

Two independent features for the Point of Sale.

**Salesperson Assignment.** A cashier attributes each sold item to the salesperson who helped the customer. This is used for commission and performance tracking. The cashier can attribute one line, or all lines of the order in one action. The assignment is stored on the order line in the backend and printed on the receipt under the product. It works offline, like the rest of the POS.

**Enhanced Receipt Layout.** A shop can switch its receipt to a branded layout:
- its own logo;
- company name and details;
- customer name and address;
- products in a clear table.

When the option is off, the receipt stays exactly the native Odoo receipt.

Both features are toggled per POS configuration. Each one must look and behave like a native part of Odoo 20.

## 2. Goals

1. Every requirement in Exercise 3 §2–§3 and test cases 1–5 passes on Odoo 20.
2. The two modules are installable independently and together. Installed together, they compose without a bridge module: the salesperson name also appears inside the enhanced table.
3. With a feature off, POS UI and receipt are identical to native Odoo (backward compatibility).
4. Salespersons are available offline: loaded with the POS data, assigned without server calls, synced with the order.
5. Automated tests cover the backend (models, load data, order sync, receipt rendering) and the POS UI (tours).

## 3. Non-goals

- Commission computation or salesperson reports. Backend visibility on the order lines is enough.
- Salesperson permissions or PIN login. `pos_hr` already covers cashiers.
- Changing kitchen or preparation tickets.

## 4. Anti-goals

- Editing native templates or JS files. Only inheritance and `patch()` are allowed.
- A receipt that breaks or duplicates content when both modules are installed.
- Raw HTML from configuration rendered unsanitised (XSS on receipts and in the backend).
- Loading every salesperson of the database into every POS. Only the allowed ones are loaded.

## 5. Decisions made with the user

### 5.1 Assignment behaviour (the user's words, summarised)

- **"Assign Salesperson to Order"** assigns the chosen salesperson to **all current lines**. It also stores them as the **order salesperson**: every line added afterwards gets them automatically.
- **The per-line icon** assigns a salesperson to **that line only**. It does not change the order salesperson, and it does not affect lines added later.
- **A line changed individually keeps its value** (Ahmed → Mohamed stays Mohamed) when new lines are added.
- **Pressing "Assign to Order" again overwrites every line, including individually changed ones.** This is assessment test case 3 (global overwrites individual). It is written down as the policy.

### 5.2 Receipt look (approved on a mockup)

**Original layout** (enhanced receipt off): native receipt, unchanged. With the salesperson feature on, `Salesperson: <name>` is printed under the product name of each assigned line.

**Enhanced layout** (on), top to bottom:
1. Receipt logo.
2. Company name.
3. Company details.
4. Customer name and address (when `show_customer_details`).
5. Ticket reference and date.
6. A table with the columns **Product | Qty | Price | Total**. The salesperson name sits under the product name inside the Product cell. Discount and customer note also stay inside the Product cell, as small lines, like native.
7. Below the table: totals, taxes, payments and footer, all native.

## 6. Salesperson module — `azk_pos_salesperson`

Depends on `point_of_sale` and `hr`.

### Data model

**New model `pos.sale.person`.** It inherits `pos.load.mixin`.

| Field | Definition |
|---|---|
| `name` | Char, required |
| `phone_number` | Char |
| `employee_id` | Many2one `hr.employee`, optional |
| `active` | Boolean, default True. This is my call: lets a salesperson who left be archived without breaking old orders. |
| `company_id` | Many2one `res.company`, default the current company. This is my call: multi-company POS. |

**`pos.config`:**
- `active_salesperson_feature` (Boolean).
- `allowed_sale_person_ids` (Many2many `pos.sale.person`).

**`pos.order.line`:** `salesperson_id` (Many2one `pos.sale.person`, `ondelete='restrict'`), added to `_load_pos_data_fields`.

**`pos.order`:** `salesperson_id` (Many2one `pos.sale.person`), the order salesperson from §5.1. This is my call. The spec only names the line field, but the user's "new lines inherit" rule needs the order salesperson to survive a page reload or an offline restart. That makes it part of the synced order. It is also shown on the order form.

### Loading (offline)

- `pos.session._load_pos_data_models` adds `pos.sale.person`.
- Domain: the config's `allowed_sale_person_ids` when the feature is active, otherwise nothing.
- Fields: `name`, `phone_number`, `employee_id`.
- Serialization of `salesperson_id` on lines and orders happens through the native related-models serializer. No custom sync code.

### Assignment UI (product screen; feature active only)

**Line icon.** A person icon on each order line in the product screen, via an `Orderline` template extension.
- Clicking it opens the selection popup for that line.
- The click must not also select or long-press the line.
- When assigned, the salesperson name is shown on the line on screen.

**Order button.** An "Assign Salesperson to Order" button among the product-screen control buttons, via a `ControlButtons` template extension and patch.

**The popup.**
- It is the native `SelectionPopup` (`makeAwaitable(dialog, SelectionPopup, {title, list})`).
- It lists the allowed salespersons, plus a first entry **"No salesperson"** that clears the value.
- The current value is pre-selected.
- Closing the popup changes nothing.

**Applying the choice.**
- On a line: sets the line's `salesperson_id`.
- From the order button: sets `order.salesperson_id`, and sets `salesperson_id` on every line. "No salesperson" clears both.

**New lines.** When a line is added, it takes `order.salesperson_id` if set. This is a patch on the order/line creation path.

**Line merging.** Adding the same product again merges into an existing line only when that line has the same salesperson. Otherwise a new line is created. This is my call, so that two salespersons selling the same product are not merged into one line.

**Feature off.** No icon, no button, and lines keep no salesperson.

### Backend views

- **`pos.sale.person`:** list, form and search views (search by name, phone and employee). Menu at *Point of Sale › Configuration › Salespersons*.
- **`pos.order.line`:** the list view shows a `salesperson_id` column. The `pos.order` form also shows the order salesperson and the line column.
- **`pos.config`:** form view (`point_of_sale.pos_config_view_form`) shows the toggle, and the allowed salespersons (visible when the toggle is on).
- **POS Settings page** (`res.config.settings`): the same two settings, through `pos_`-prefixed related fields. This is my call: in Odoo 20 that page is where POS options are usually edited.

### Receipt

- A template extension of `point_of_sale.pos_orderline_receipt_information` prints `Salesperson: <name>` in its `extra-info` slot. It prints only when the config feature is active and the line has a salesperson.
- The line data gains `salesperson_name`, in both places:
  - the JS generator (`generateLineData` patch);
  - the Python mirror (`pos.order.receipt` line data, used by email and download receipts).

### Security

`security/ir.access.csv` (Odoo 20 format):
- `pos.sale.person`: read for `point_of_sale.group_pos_user`; full access for `point_of_sale.group_pos_manager`.

## 7. Enhanced receipt module — `azk_pos_enhanced_receipt`

Depends on `point_of_sale`.

### Data model (`pos.config`)

| Field | Type |
|---|---|
| `use_customized_receipt` | Boolean |
| `receipt_logo` | Binary (image) |
| `company_name` | **Html**, sanitized |
| `company_details` | **Html**, sanitized |
| `show_customer_details` | Boolean |

`company_name` and `company_details` deviate from the spec's "Text": they are **Html with Odoo's sanitizer**. The spec says these "can be HTML code", and rendering unsanitized HTML is an XSS risk. The README documents this. Native `pos.config` already has `custom_logo`, `logo` and `use_custom_receipt_info`; the new names do not clash (to be verified).

### Receipt (template extensions only)

**Header (`pos_order_receipt_header`).**
- When `use_customized_receipt`, the logo is replaced by `receipt_logo`. If `receipt_logo` is empty, the native logo stays.
- Then come company name, company details (rendered as sanitized markup) and, when `show_customer_details`, the customer name and address.

**Lines (`pos_order_receipt`).** When `use_customized_receipt`, the per-line `<table>` loop is replaced by one table with a header row (Product | Qty | Price | Total).
- The Product cell reuses `point_of_sale.pos_orderline_receipt_information`. Name, discount, notes and any addon's `extra-info` content, including the salesperson, therefore appear with no coupling between the modules.
- The standard unit-price line inside that template is hidden in table mode, because the Price column carries it.
- Combo children render as indented rows.

**Option off.** The native templates render unchanged.

**Data.** Both the JS generator and the Python mirror must expose:
- the logo source (offline-safe on the client);
- the markup-safe HTML of `company_name` and `company_details`;
- the customer address.

**Settings.** Same pattern as §6: `pos.config` form plus the POS Settings page.

**Security.** No new model.

## 8. Conflicts when both are installed (README answer)

What could conflict, and how this design avoids each one:

1. **Same receipt templates extended by two modules.**
   - The salesperson module only appends inside `extra-info`.
   - The enhanced module replaces the line loop, but re-uses `pos_orderline_receipt_information`.
   - So the salesperson name survives the table layout.
   - Wider rule: an xpath must target stable `name`d hooks, never a template another addon replaces.
2. **Both patching the receipt data generator (JS and Python).** Each patch calls `super` and adds its own keys only.
3. **Both adding settings to the same `pos.config` form and POS Settings block.** Separate `<setting>` ids, positioned relative to native anchors.
4. **Field name clashes with native or other addons.** Unique names, checked against `pos.config`.
5. **Load order.** Neither module depends on the other. If a future need forces an order, use a small auto-install **bridge module** depending on both. This is the standard Odoo resolution; it is not needed here.

## 9. Testing

**Python, model level.**
- Load data contains only the allowed salespersons, and only when the feature is active.
- `sync_from_ui` with a line `salesperson_id` stores it; the order salesperson too.
- Python receipt data has `salesperson_name`.
- Rendering the receipt template server-side shows the name under the product only when the feature is on.
- Enhanced receipt:
  - The rendered HTML contains the logo, company info, customer details and the table when the option is on.
  - It equals the native output when the option is off.
  - With both modules, the table contains the salesperson.
  - Html fields are sanitized (a `<script>` is stripped).
- Access rights.

**POS tours (`HttpCase`, `start_pos_tour`).** These are assessment test cases 1–5:
1. Visibility per config.
2. Per-line assignment, then validation, then backend values.
3. Global assignment overwriting individual assignments.
4. No assignment.
5. Config changed during an open session: no effect until reload.

Plus a tour for the user's rule: a line added after "Assign to Order" inherits the salesperson; a manually changed line keeps its value.

The four configs of §4.1 (`POS_Sales_Enabled_Enhanced_Receipt`, …) are created in the test setup. The README walks through them manually.

## 10. Builder's calls (made during design)

- **Order-level `salesperson_id`** (§6). Needed for the user's inheritance rule to survive reloads.
- **"No salesperson" entry in the popup**, as a way to clear a value.
- **Merge rule:** same product merges only with the same salesperson.
- **`active` and `company_id` on `pos.sale.person`.**
- **Html (sanitized)** instead of Text for company name and details.
- **Settings on both** the `pos.config` form and the POS Settings page.

### Settled after the builder check

**Enhanced header replaces the native header blocks, it does not sit next to them** (no duplicates).
- When `use_customized_receipt` is on:
  - the native logo is replaced by `receipt_logo`, falling back to the native logo when empty;
  - the native `partner_info` block (customer name/VAT) is replaced by our customer block;
  - the native footer company block (`company_info_receipt`) is hidden, because company name and details are printed at the top instead.
- With `show_customer_details` off, no customer block is printed at all. That is the spec's meaning of the flag.
- Cashier, preset, tracking number, ticket reference and date stay native.

**Salesperson feature off:**
- no icon, no button, nothing printed;
- new lines get no salesperson;
- values already stored in the database are kept (history), never cleared.

**Reprint of an older order whose salesperson is no longer allowed in the config:**
- the client prints the name only if that salesperson is loaded. The load domain stays "allowed ones only" (anti-goal §4).
- server-side receipts (email/download) read the name from the database.

**Basic receipt** (`conditions['basic_receipt']`, prices hidden): the salesperson line still prints. The enhanced table drops its Price and Total columns, mirroring native, and keeps Product | Qty.

**Price column:** follows the native receipt (unit price as displayed natively; tax-included or not per the POS setting).

**"Assign to Order" on an empty order** only sets the order salesperson, which then applies to the lines added next.

### Assessment configs and test cases (verbatim source: PDF §4)

**Configurations:**

| Config | `active_salesperson_feature` | `allowed_sale_person_ids` | `use_customized_receipt` | Receipt fields |
|---|---|---|---|---|
| `POS_Sales_Enabled_Enhanced_Receipt` | ✓ | Salesperson A, B | ✓ | `receipt_logo`, `company_name`, `company_details` and `show_customer_details` set |
| `POS_Sales_Enabled_Default_Receipt` | ✓ | set | ✗ | — |
| `POS_Sales_Disabled_Enhanced_Receipt` | ✗ | — | ✓ | logo, company name/details, customer details on |
| `POS_All_Disabled` | ✗ | values may be set, must be ignored | ✗ | values may be set, must be ignored |

Salespersons "Salesperson A", "B" and "C" exist in the backend.

**Test cases:**
1. **Visibility per config.**
   - Enabled + Enhanced: line icon and button visible; the receipt shows logo, company info, customer details, table and names.
   - Disabled + Enhanced: UI hidden; enhanced receipt.
   - Enabled + Default: UI visible; original receipt with no logo/company info, list lines.
   - All disabled: nothing.
2. **Individual assignment.** Product X gets A, product Y gets B. Check the screen, the printed receipt and the backend `salesperson_id` per line.
3. **Global overwrites individual.** C gets A and D gets B individually, then global "Salesperson C". Both lines show C on screen, on the receipt and in the database.
4. **No assignment.** No name anywhere; `salesperson_id` empty in the backend.
5. **Config change during an open session.**
   - Start `POS_All_Disabled`, then enable both features in the backend without closing the session, then complete a sale.
   - The receipt is original and there is no salesperson UI. Changes need a POS reload, i.e. a browser refresh of the POS, which reloads the POS data.

## 11. Left to the builder

- Exact template anchors and xpaths, icon choice (Tabler/Font Awesome as used by Odoo 20 POS), CSS file content (optional per spec).
- Whether the logo on the client is served as a data URL or a URL. It must print offline the same way native `receiptLogoUrl` does.
- Tour step helpers and test data volumes.
