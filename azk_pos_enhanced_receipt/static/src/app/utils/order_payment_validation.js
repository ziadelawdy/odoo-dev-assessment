import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { isValidEmail } from "@point_of_sale/utils";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";

patch(OrderPaymentValidation.prototype, {
    async afterOrderValidation(...args) {
        const result = await super.afterOrderValidation(...args);
        if (this.pos.config.azk_auto_email_receipt) {
            // fire and forget: the cashier never waits for the mail
            this.azkAutoEmailReceipt();
        }
        return result;
    },

    /**
     * Emails the receipt with the native "send receipt" action.
     *
     * @returns {false|Promise} false when nothing is sent: no customer email,
     *   or the order is not on the server yet (offline), which the native
     *   "Send receipt" button can still handle later.
     */
    azkAutoEmailReceipt() {
        const order = this.order;
        const email = order?.partner_id?.email;
        if (!email || !isValidEmail(email) || !order.isSynced) {
            return false;
        }
        return this.pos.data
            .call("pos.order", "action_send_receipt", [[order.id], email])
            .then(() => {
                this.pos.notification.add(_t("Receipt sent to %s", email), { type: "success" });
            })
            .catch(() => {
                this.pos.notification.add(_t("The receipt could not be emailed to %s.", email), {
                    type: "warning",
                });
            });
    },
});
