import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as FeedbackScreen from "@point_of_sale/../tests/pos/tours/utils/feedback_screen_util";
import * as combo from "@point_of_sale/../tests/pos/tours/utils/combo_popup_util";
import { negate, refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const line = (product) => `.order-container .orderline:has(.product-name:contains("${product}"))`;

const assignLine = (product, person) => [
    {
        content: `open salesperson popup on ${product}`,
        trigger: `${line(product)} .azk-salesperson-btn`,
        run: "click",
    },
    {
        content: `choose ${person}`,
        trigger: `.modal .selection-item:contains("${person}")`,
        run: "click",
    },
];

const assignOrder = (person) => [
    {
        content: "open order salesperson popup",
        trigger: ".azk-assign-order-salesperson",
        run: "click",
    },
    {
        content: `choose ${person} for the order`,
        trigger: `.modal .selection-item:contains("${person}")`,
        run: "click",
    },
];

const lineShows = (product, person) => ({
    content: `${product} shows ${person}`,
    trigger: `${line(product)} .azk-salesperson-name:contains("${person}")`,
});

const lineShowsNothing = (product) => ({
    content: `${product} has no salesperson`,
    trigger: `${line(product)}:not(:has(.azk-salesperson-name))`,
});

const open = () => [Chrome.startPoS(), Dialog.confirm("Open Register")];

const pay = () => [
    ProductScreen.clickPayButton(),
    PaymentScreen.clickPaymentMethod("Bank"),
    PaymentScreen.clickValidate(),
    FeedbackScreen.isShown(),
];

registry.category("web_tour.tours").add("AzkSalespersonLineTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            assignLine("Whiteboard Pen", "Salesperson A"),
            lineShows("Whiteboard Pen", "Salesperson A"),
            ProductScreen.clickDisplayedProduct("Letter Tray"),
            assignLine("Letter Tray", "Salesperson B"),
            lineShows("Letter Tray", "Salesperson B"),
            lineShows("Whiteboard Pen", "Salesperson A"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonGlobalTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Desk Organizer"),
            assignLine("Desk Organizer", "Salesperson A"),
            ProductScreen.clickDisplayedProduct("Wall Shelf Unit"),
            assignLine("Wall Shelf Unit", "Salesperson B"),
            lineShows("Desk Organizer", "Salesperson A"),
            lineShows("Wall Shelf Unit", "Salesperson B"),
            assignOrder("Salesperson C"),
            lineShows("Desk Organizer", "Salesperson C"),
            lineShows("Wall Shelf Unit", "Salesperson C"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonNoneTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            ProductScreen.clickDisplayedProduct("Letter Tray"),
            lineShowsNothing("Whiteboard Pen"),
            lineShowsNothing("Letter Tray"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonInheritTour", {
    steps: () =>
        [
            open(),
            assignOrder("Salesperson A"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            lineShows("Whiteboard Pen", "Salesperson A"),
            assignLine("Whiteboard Pen", "Salesperson B"),
            ProductScreen.clickDisplayedProduct("Letter Tray"),
            lineShows("Letter Tray", "Salesperson A"),
            lineShows("Whiteboard Pen", "Salesperson B"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonMergeTour", {
    steps: () =>
        [
            open(),
            assignOrder("Salesperson A"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            assignLine("Whiteboard Pen", "Salesperson B"),
            // order salesperson A differs from the existing B line: new line
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            // same salesperson A: merges into the A line
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            // a line shows a single name: both names visible = two separate lines
            lineShows("Whiteboard Pen", "Salesperson B"),
            lineShows("Whiteboard Pen", "Salesperson A"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonComboTour", {
    steps: () =>
        [
            open(),
            assignOrder("Salesperson C"),
            ProductScreen.clickDisplayedProduct("Office Combo"),
            combo.select("Combo Product 3"),
            combo.select("Combo Product 5"),
            combo.select("Combo Product 8"),
            Dialog.confirm(),
            // combo children inherit the order salesperson
            lineShows("Combo Product 3", "Salesperson C"),
            // assigning the combo parent also assigns its children
            assignLine("Office Combo", "Salesperson A"),
            lineShows("Combo Product 3", "Salesperson A"),
            lineShows("Combo Product 8", "Salesperson A"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonReloadTour", {
    steps: () =>
        [
            open(),
            assignOrder("Salesperson A"),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            assignLine("Whiteboard Pen", "Salesperson B"),
            refresh(),
            lineShows("Whiteboard Pen", "Salesperson B"),
            ProductScreen.clickDisplayedProduct("Letter Tray"),
            lineShows("Letter Tray", "Salesperson A"),
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});

registry.category("web_tour.tours").add("AzkSalespersonHiddenTour", {
    steps: () =>
        [
            open(),
            ProductScreen.clickDisplayedProduct("Whiteboard Pen"),
            {
                content: "no line icon",
                trigger: negate(".azk-salesperson-btn"),
            },
            {
                content: "no order button",
                trigger: negate(".azk-assign-order-salesperson"),
            },
            pay(),
            Chrome.endTour(),
        ].flat(Infinity),
});
