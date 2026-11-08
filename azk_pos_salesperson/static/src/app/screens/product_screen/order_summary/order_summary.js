import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { selectSalesperson } from "@azk_pos_salesperson/app/utils/salesperson_popup";

patch(OrderSummary.prototype, {
    async azkAssignLineSalesperson(line) {
        const person = await selectSalesperson(this.pos, this.dialog, line.salesperson_id, _t("Salesperson for this line"));
        if (person !== undefined) {
            line.setSalesperson(person);
        }
    },
});
