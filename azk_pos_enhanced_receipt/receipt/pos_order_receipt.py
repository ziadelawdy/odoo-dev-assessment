from markupsafe import Markup

from odoo import models
from odoo.tools import is_html_empty
from odoo.tools.image import image_data_uri


class PosOrderReceipt(models.AbstractModel):
    """Python mirror of the customized receipt data (email / download receipts).

    Keep in sync with static/src/app/utils/printer/generate_printer_data.js.
    """
    _inherit = 'pos.order.receipt'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt=basic_receipt)
        config = self.config_id
        enhanced = bool(config.use_customized_receipt)
        data['conditions']['azk_enhanced'] = enhanced
        data['conditions']['azk_show_customer'] = enhanced and bool(config.show_customer_details)
        if not enhanced:
            return data
        if config.receipt_logo:
            data['image']['logo'] = image_data_uri(config.receipt_logo)
        elif config.azk_logo_is_placeholder:
            # never print Odoo's "Your logo" placeholder on the customized receipt
            data['image']['logo'] = False
        data['extra_data'].update({
            # stored sanitized (fields.Html), so safe to render as markup
            'azk_company_name': self._azk_html(config.company_name),
            'azk_company_details': self._azk_html(config.company_details),
            'azk_customer': self._azk_customer_data(),
        })
        return data

    @staticmethod
    def _azk_html(value):
        return Markup(value) if value and not is_html_empty(value) else False

    def _azk_customer_data(self):
        partner = self.partner_id
        if not partner:
            return False
        city_line = ' '.join(part for part in (partner.zip, partner.city) if part)
        address = [partner.street, partner.street2, city_line, partner.country_id.name]
        return {'name': partner.name, 'address_lines': [line for line in address if line]}
