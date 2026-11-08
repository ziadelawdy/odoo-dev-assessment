import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrderline.prototype, {
    /** Assign (or clear with `null`) the salesperson of this line and its combo children. */
    setSalesperson(person) {
        this.salesperson_id = person || false;
        for (const child of this.combo_line_ids || []) {
            child.salesperson_id = person || false;
        }
    },
    /** A product only merges into a line credited to the same salesperson. */
    canBeMergedWith(orderline) {
        if ((this.salesperson_id?.id || false) !== (orderline.salesperson_id?.id || false)) {
            return false;
        }
        return super.canBeMergedWith(...arguments);
    },
});
