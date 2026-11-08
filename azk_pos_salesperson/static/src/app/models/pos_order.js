import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    /**
     * "Assign Salesperson to Order": becomes the order salesperson (inherited by
     * lines added later) and overwrites every current line (assessment test case 3).
     */
    setSalespersonOnAllLines(person) {
        this.salesperson_id = person || false;
        for (const line of this.lines) {
            line.setSalesperson(person);
        }
    },
});
