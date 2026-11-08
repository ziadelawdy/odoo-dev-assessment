import { _t } from "@web/core/l10n/translation";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";

/**
 * Ask the cashier for a salesperson among the ones loaded for this POS.
 *
 * @returns {Promise<Object|null|undefined>} the salesperson record, `null` for
 *   "No salesperson", or `undefined` when the popup is closed (no change).
 */
export async function selectSalesperson(pos, dialog, current, title) {
    const persons = pos.models["pos.sale.person"].getAll();
    const list = [
        { id: 0, label: _t("No salesperson"), isSelected: !current, item: null },
        ...persons.map((person) => ({
            id: person.id,
            label: person.name,
            isSelected: current?.id === person.id,
            item: person,
        })),
    ];
    return makeAwaitable(dialog, SelectionPopup, {
        title: title || _t("Select a salesperson"),
        list,
    });
}
