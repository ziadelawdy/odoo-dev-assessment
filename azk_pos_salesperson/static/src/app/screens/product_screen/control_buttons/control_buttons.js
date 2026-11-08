import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { selectSalesperson } from "@azk_pos_salesperson/app/utils/salesperson_popup";

patch(ControlButtons.prototype, {
    async azkAssignOrderSalesperson() {
        const order = this.pos.getOrder();
        const person = await selectSalesperson(this.pos, this.dialog, order.salesperson_id, _t("Salesperson for the whole order"));
        if (person !== undefined) {
            order.setSalespersonOnAllLines(person);
        }
    },
});
