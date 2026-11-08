import base64

from odoo.tools import BinaryBytes

from odoo.addons.point_of_sale.tests.common import TestPoSCommon

# 1x1 PNG pixels, distinct so the rendered data URI tells which logo was used
NATIVE_LOGO = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)
RECEIPT_LOGO = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
)


class AzkEnhancedReceiptCommon(TestPoSCommon):
    """Basic POS config, a customer with an address, helpers to sync and render orders."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.config.logo = BinaryBytes(NATIVE_LOGO)
        cls.customer = cls.env['res.partner'].create({
            'name': 'Sara Ali',
            'street': '5 Nile St',
            'city': 'Giza',
            'zip': '12511',
        })
        cls.product_x = cls.create_product('Product X', cls.categ_basic, 10.0)
        cls.product_y = cls.create_product('Product Y', cls.categ_basic, 20.0)

    def _enable(self, **values):
        self.config.write({
            'use_customized_receipt': True,
            'receipt_logo': BinaryBytes(RECEIPT_LOGO),
            'company_name': '<p>NOX Trading</p>',
            'company_details': '<p><b>12 Tahrir St</b></p>',
            'show_customer_details': True,
            **values,
        })

    def _sync_order(self, lines, customer=None, line_extra=None):
        """lines: list of (product, qty)."""
        line_args = [{'product': product, 'quantity': qty, **(line_extra or {})} for product, qty in lines]
        data = self.create_ui_order_data(line_args, customer=customer)
        result = self.env['pos.order'].sync_from_ui([data])
        return self.env['pos.order'].browse(result['pos.order'][0]['id'])

    @staticmethod
    def _render(order, basic_receipt=False):
        return str(order.order_receipt_generate_html(basic_receipt=basic_receipt))
