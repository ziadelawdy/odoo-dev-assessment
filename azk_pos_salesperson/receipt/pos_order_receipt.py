from odoo import models


class PosOrderReceipt(models.AbstractModel):
    """Python mirror of the client receipt data (email / download receipts).

    Keep in sync with static/src/app/utils/printer/generate_printer_data.js.
    """
    _inherit = 'pos.order.receipt'

    def _order_receipt_generate_line_data(self):
        lines = super()._order_receipt_generate_line_data()
        for data, line in zip(lines, self.lines):
            data['salesperson_name'] = line.salesperson_id.name or False
        return lines

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt=basic_receipt)
        data['conditions']['azk_salesperson'] = self.config_id.active_salesperson_feature
        return data
