import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { selectSalesperson } from "@azk_pos_salesperson/app/utils/salesperson_popup";

patch(PosStore.prototype, {
    /**
     * Ask when a product is added to an order that has no salesperson and
     * whose cashier has not answered the question yet (closing the popup is
     * not an answer; "No salesperson" is).
     */
    azkShouldAskSalesperson(vals, order) {
        return Boolean(
            this.config.active_salesperson_feature &&
                order &&
                !order.salesperson_id &&
                !order.uiState?.azkSalespersonAnswered &&
                !("salesperson_id" in vals) &&
                this.models["pos.sale.person"].getAll().length
        );
    },
    /** New lines are credited to the order salesperson, if one was set. */
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        if (this.azkShouldAskSalesperson(vals, order)) {
            // the answer becomes the order salesperson (all lines so far);
            // "No salesperson" (null) stops the question for this order,
            // closing the popup (undefined) asks again with the next product
            const chosen = await selectSalesperson(this, this.dialog, null, _t("Who is the salesperson for this order?"));
            if (chosen !== undefined) {
                order.uiState.azkSalespersonAnswered = true;
            }
            if (chosen) {
                order.setSalespersonOnAllLines(chosen);
            }
        }
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
