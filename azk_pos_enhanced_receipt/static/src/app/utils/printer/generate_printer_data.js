import { markup } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { imageDataUri } from "@point_of_sale/utils";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

const isEmptyHtml = (value) => !value || !value.replace(/<[^>]*>|&nbsp;|\s/g, "");

/**
 * Client side of the customized receipt data (keep in sync with receipt/pos_order_receipt.py).
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const config = this.config;
        const enhanced = Boolean(config.use_customized_receipt);
        data.conditions.azk_enhanced = enhanced;
        data.conditions.azk_show_customer = enhanced && Boolean(config.show_customer_details);
        if (!enhanced) {
            return data;
        }
        if (config.receipt_logo?.content) {
            data.image.logo = imageDataUri(config.receipt_logo.content);
        } else if (config.azk_logo_is_placeholder) {
            // never print Odoo's "Your logo" placeholder on the customized receipt
            data.image.logo = false;
        }
        // stored sanitized by the server (fields.Html): safe to render as markup
        data.extra_data.azk_company_name = isEmptyHtml(config.company_name) ? false : markup(config.company_name);
        data.extra_data.azk_company_details = isEmptyHtml(config.company_details)
            ? false
            : markup(config.company_details);
        const partner = this.order.partner_id;
        data.extra_data.azk_customer = partner
            ? {
                  name: partner.name,
                  address_lines: [
                      partner.street,
                      partner.street2,
                      [partner.zip, partner.city].filter(Boolean).join(" "),
                      partner.country_id?.name,
                  ].filter(Boolean),
              }
            : false;
        return data;
    },
});
