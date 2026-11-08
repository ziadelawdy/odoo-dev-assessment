import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * Client side of the receipt data (keep in sync with receipt/pos_order_receipt.py).
 */
patch(GeneratePrinterData.prototype, {
    generateLineData() {
        const lines = super.generateLineData(...arguments);
        this.order.lines.forEach((line, index) => {
            lines[index].salesperson_name = line.salesperson_id?.name || false;
        });
        return lines;
    },
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.azk_salesperson = Boolean(this.config.active_salesperson_feature);
        return data;
    },
});
