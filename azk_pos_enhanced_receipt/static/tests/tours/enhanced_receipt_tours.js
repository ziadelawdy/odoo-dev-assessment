import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import { negate } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

/**
 * Assessment test cases 1 and 5 (both modules installed). The receipt is
 * rendered by the client, exactly like the printed / on-screen receipt.
 */

const open = () => [Chrome.startPoS(), Dialog.confirm("Open Register")];

const salespersonUi = (visible) =>
    visible
        ? [
              { content: "line icon visible", trigger: ".azk-salesperson-btn" },
              { content: "order button visible", trigger: ".azk-assign-order-salesperson" },
          ]
        : [
              { content: "no line icon", trigger: negate(".azk-salesperson-btn") },
              { content: "no order button", trigger: negate(".azk-assign-order-salesperson") },
          ];

const assignOrder = (person) => [
    { content: "open order salesperson popup", trigger: ".azk-assign-order-salesperson", run: "click" },
    { content: `choose ${person}`, trigger: `.modal .selection-item:contains("${person}")`, run: "click" },
];

const pickCustomer = () => [
    ProductScreen.clickPartnerButton(),
    ProductScreen.clickCustomer("APartner Full", true),
];

const pay = () => [
    ProductScreen.clickPayButton(),
    PaymentScreen.clickPaymentMethod("Bank"),
    PaymentScreen.clickValidate(),
    FeedbackScreen.isShown(),
];

/**
 * checks: { present: [selector], absent: [selector], texts: [[selector, text]] }
 */
const checkReceipt = (checks) => ({
    content: "check the client-rendered receipt",
    trigger: ".pos .feedback-screen",
    run: async () => {
        const order = posmodel.getOrder();
        const data = posmodel.ticketPrinter.getOrderReceiptData(order, {});
        const iframe = await posmodel.ticketPrinter.generateIframe("point_of_sale.pos_order_receipt", data);
        const ticket = (iframe.contentDocument || iframe.contentWindow.document).getElementById("pos-receipt");
        for (const selector of checks.present || []) {
            if (!ticket.querySelector(selector)) {
                throw new Error(`Receipt: ${selector} expected`);
            }
        }
        for (const selector of checks.absent || []) {
            if (ticket.querySelector(selector)) {
                throw new Error(`Receipt: ${selector} not expected`);
            }
        }
        for (const [selector, text] of checks.texts || []) {
            const found = [...ticket.querySelectorAll(selector)].some((el) => el.textContent.includes(text));
            if (!found) {
                throw new Error(`Receipt: "${text}" expected in ${selector}`);
            }
        }
    },
});

const ENHANCED = [".azk-company", ".azk-lines-table"];

registry.category("web_tour.tours").add("AzkTc1EnabledEnhancedTour", {
    steps: () =>
        [
            open(),
            pickCustomer(),
            assignOrder("Salesperson A"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            salespersonUi(true),
            pay(),
            checkReceipt({
                present: [...ENHANCED, ".azk-customer", ".azk-lines-table .azk-salesperson"],
                absent: ['[name="partner_info"]', '[name="company_info"]'],
                texts: [
                    [".azk-company", "NOX Trading"],
                    [".azk-customer", "77 Santa Barbara Rd"],
                    [".azk-lines-table .azk-salesperson", "Salesperson A"],
                    [".azk-lines-table th", "Price"],
                ],
            }),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkTc1DisabledEnhancedTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            salespersonUi(false),
            pay(),
            checkReceipt({ present: ENHANCED, absent: [".azk-salesperson"] }),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkTc1EnabledDefaultTour", {
    steps: () =>
        [
            open(),
            assignOrder("Salesperson A"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            salespersonUi(true),
            pay(),
            checkReceipt({
                present: ['[name="standard-line"]', ".azk-salesperson"],
                absent: ENHANCED,
                texts: [[".azk-salesperson", "Salesperson A"]],
            }),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkTc1AllDisabledTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            salespersonUi(false),
            pay(),
            checkReceipt({ present: ['[name="standard-line"]'], absent: [...ENHANCED, ".azk-salesperson"] }),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkTc5ConfigChangeTour", {
    steps: () =>
        [
            open(),
            {
                content: "enable both features in the backend while the POS session stays open",
                trigger: ".pos .product-screen",
                run: async () => {
                    await posmodel.data.call("pos.config", "write", [
                        [posmodel.config.id],
                        { active_salesperson_feature: true, use_customized_receipt: true },
                    ]);
                },
            },
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            salespersonUi(false),
            pay(),
            checkReceipt({ present: ['[name="standard-line"]'], absent: [...ENHANCED, ".azk-salesperson"] }),
            Chrome.endTour(),
        ].flat(Infinity),
});
