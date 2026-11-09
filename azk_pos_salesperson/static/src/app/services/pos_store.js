import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    /** New lines are credited to the order salesperson, if one was set. */
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const person = this.config.active_salesperson_feature ? order?.salesperson_id : false;
        const inherit = person && !("salesperson_id" in vals);
        if (inherit) {
            // set before creation so the merge check compares salespersons
            vals = { ...vals, salesperson_id: person };
        }
        const line = await super.addLineToOrder(vals, order, opts, configure);
        if (inherit && line) {
            // combo children are created by the combo flow: credit them too
            line.setSalesperson(person);
        }
        return line;
    },
    /**
     * Editing a combo (long press) re-creates its children through this method:
     * credit the new children to the salesperson of the edited line.
     */
    async handleComboProduct(values, order, configure, opts = {}) {
        const result = await super.handleComboProduct(...arguments);
        const person = opts.line?.salesperson_id;
        if (result !== false && person && Array.isArray(values.combo_line_ids)) {
            for (const command of values.combo_line_ids) {
                if (Array.isArray(command) && command[0] === "create" && command[1]) {
                    command[1].salesperson_id = person;
                }
            }
        }
        return result;
    },
});
