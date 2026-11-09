import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

patch(TicketScreen.prototype, {
    /** A POS refund stays credited to the salesperson of the refunded line (like backend refunds). */
    getRefundLinesDetails(refundDetail, destinationOrder) {
        const details = super.getRefundLinesDetails(...arguments);
        if (refundDetail.line.salesperson_id) {
            details.salesperson_id = refundDetail.line.salesperson_id;
        }
        return details;
    },
});
