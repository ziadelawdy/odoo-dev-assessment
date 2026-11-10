import { Component, onWillUnmount, signal, useEffect, useProps, t } from "@odoo/owl";
import { renderToElement } from "@web/core/utils/render";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

const RENDER_DELAY = 150;

/**
 * Live preview of the order receipt, rendered with the same template and
 * data as printing, in its own iframe (the print iframe container is left
 * alone).
 */
export class AzkReceiptPreview extends Component {
    static template = "azk_pos_enhanced_receipt.ReceiptPreview";
    props = useProps({ order: t.object() });
    frame = signal.ref();

    setup() {
        this.pos = usePos();
        this.timer = null;
        useEffect(() => {
            // reading the signature subscribes the effect to the order changes
            this.azkSignature();
            if (!this.frame()) {
                return;
            }
            clearTimeout(this.timer);
            this.timer = setTimeout(() => this.azkRender(), RENDER_DELAY);
        });
        onWillUnmount(() => clearTimeout(this.timer));
    }

    /** Everything the printed receipt depends on that changes while paying. */
    azkSignature() {
        const order = this.props.order;
        return JSON.stringify([
            order.partner_id?.id,
            order.amount_total,
            order.lines.map((line) => [line.uuid, line.qty, line.price_unit, line.salesperson_id?.id]),
            order.payment_ids.map((payment) => [payment.uuid, payment.amount, payment.payment_method_id?.id]),
        ]);
    }

    azkRender() {
        const iframe = this.frame();
        if (!iframe) {
            return;
        }
        const data = this.pos.ticketPrinter.getOrderReceiptData(this.props.order);
        // the order is still a draft: hide the "Pro forma receipt" label
        data.conditions.azk_preview = true;
        // a new srcdoc reloads the document at the top: keep the cashier's
        // scroll position (the totals are at the bottom of a long receipt)
        const scrollTop = iframe.contentDocument?.scrollingElement?.scrollTop || 0;
        iframe.onload = () => {
            const scroller = iframe.contentDocument?.scrollingElement;
            if (scroller && scrollTop) {
                scroller.scrollTop = scrollTop;
            }
        };
        iframe.srcdoc = renderToElement("point_of_sale.pos_order_receipt", data).outerHTML;
    }
}
