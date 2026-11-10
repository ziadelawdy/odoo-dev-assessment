import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { registry } from "@web/core/registry";

/** Checkout flow: live receipt preview on the payment screen, automatic email. */

const open = () => [Chrome.startPoS(), Dialog.confirm("Open Register")];

const pickCustomer = (name) => [ProductScreen.clickPartnerButton(), ProductScreen.clickCustomer(name, true)];

const previewDoc = () => {
    const iframe = document.querySelector(".payment-screen .azk-receipt-preview iframe");
    return iframe && (iframe.contentDocument || iframe.contentWindow.document);
};

/**
 * Waits (the preview re-renders debounced) until the preview receipt matches:
 * { texts: [text], absentTexts: [text], present: [selector] }
 */
const checkPreview = (label, checks) => ({
    content: `receipt preview: ${label}`,
    trigger: ".payment-screen .azk-receipt-preview iframe",
    run: async () => {
        let problem = "";
        for (let attempt = 0; attempt < 50; attempt++) {
            const doc = previewDoc();
            const body = doc?.getElementById("pos-receipt") || doc?.body;
            const text = body?.textContent || "";
            problem =
                (checks.texts || []).find((t) => !text.includes(t)) ||
                (checks.absentTexts || []).find((t) => text.includes(t)) ||
                (checks.present || []).find((s) => !body?.querySelector(s)) ||
                "";
            if (body && !problem) {
                return;
            }
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        throw new Error(`Receipt preview (${label}): unexpected "${problem}"`);
    },
});

registry.category("web_tour.tours").add("AzkPaymentPreviewTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            pickCustomer("APartner Full"),
            ProductScreen.clickPayButton(),
            checkPreview("order content", {
                texts: ["Whiteboard Pen", "APartner Full", "NOX Trading"],
                absentTexts: ["Pro forma"],
                present: [".azk-lines-table"],
            }),
            PaymentScreen.clickPaymentMethod("Bank"),
            checkPreview("follows the payment lines", { texts: ["Bank"] }),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkPaymentPreviewNativeTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            ProductScreen.clickPayButton(),
            checkPreview("native receipt", {
                texts: ["Whiteboard Pen"],
                absentTexts: ["Pro forma", "NOX Trading"],
                present: ['[name="standard-line"]'],
            }),
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkPaymentPreviewOffTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            ProductScreen.clickPayButton(),
            {
                content: "no receipt preview when the option is off",
                trigger: ".payment-screen:not(:has(.azk-receipt-preview))",
            },
            PaymentScreen.clickPaymentMethod("Bank"),
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.endTour(),
        ].flat(Infinity),
});

// ---------------------------------------------------------------------------
// Automatic email after validation
// ---------------------------------------------------------------------------

const sellToCustomer = () => [
    ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
    pickCustomer("APartner Full"),
    ProductScreen.clickPayButton(),
    PaymentScreen.clickPaymentMethod("Bank"),
    PaymentScreen.clickValidate(),
    FeedbackScreen.isShown(),
];

registry.category("web_tour.tours").add("AzkAutoEmailTour", {
    steps: () =>
        [
            open(),
            sellToCustomer(),
            {
                content: "the cashier is told the receipt was emailed",
                trigger: '.o_notification:contains("apartner@example.com")',
            },
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkAutoEmailOffTour", {
    steps: () => [open(), sellToCustomer(), Chrome.endTour()].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkAutoEmailUnsyncedTour", {
    steps: () =>
        [
            open(),
            {
                content: "an order not synced to the server is never emailed",
                trigger: ".pos .product-screen",
                run: async () => {
                    const order = posmodel.getOrder();
                    order.setPartner(posmodel.models["res.partner"].find((p) => p.name === "APartner Full"));
                    if (order.isSynced) {
                        throw new Error("the order should not be synced yet");
                    }
                    const validation = new OrderPaymentValidation({ pos: posmodel, orderUuid: order.uuid });
                    if (validation.azkAutoEmailReceipt() !== false) {
                        throw new Error("an unsynced order must not be emailed");
                    }
                },
            },
            Chrome.endTour(),
        ].flat(Infinity),
});

// ---------------------------------------------------------------------------
// Review fix: a re-render keeps the preview scroll position (totals at the bottom)
// ---------------------------------------------------------------------------

const PRODUCTS = [
    "Whiteboard Pen", "Letter Tray", "Desk Pad", "Desk Organizer", "Wall Shelf Unit",
    "Small Shelf", "Magnetic Board", "Monitor Stand",
];

registry.category("web_tour.tours").add("AzkPaymentPreviewScrollTour", {
    steps: () =>
        [
            open(),
            PRODUCTS.map((name) => ProductScreen.clickDisplayedProduct(name)),
            ProductScreen.clickPayButton(),
            checkPreview("all products", { texts: ["Monitor Stand"] }),
            {
                content: "scroll the preview to the totals",
                trigger: ".payment-screen .azk-receipt-preview iframe",
                run: () => {
                    const scroller = previewDoc().scrollingElement;
                    if (scroller.scrollHeight <= scroller.clientHeight) {
                        throw new Error("the receipt should be taller than the preview");
                    }
                    scroller.scrollTop = scroller.scrollHeight;
                },
            },
            PaymentScreen.clickPaymentMethod("Bank"),
            checkPreview("re-rendered", { texts: ["Bank"] }),
            {
                content: "the preview is still scrolled down after the re-render",
                trigger: ".payment-screen .azk-receipt-preview iframe",
                run: async () => {
                    for (let attempt = 0; attempt < 30; attempt++) {
                        if (previewDoc().scrollingElement.scrollTop > 0) {
                            return;
                        }
                        await new Promise((resolve) => setTimeout(resolve, 100));
                    }
                    throw new Error("the preview jumped back to the top");
                },
            },
            PaymentScreen.clickValidate(),
            FeedbackScreen.isShown(),
            Chrome.endTour(),
        ].flat(Infinity),
});
