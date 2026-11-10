from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    use_customized_receipt = fields.Boolean(
        string='Customized Receipt',
        help='Print receipts with the layout below (logo, company info, customer, lines table). '
             'When disabled, the standard Odoo receipt is used.',
    )
    receipt_logo = fields.Image(
        string='Receipt Logo', max_width=512, max_height=512,
        help='Printed at the top of the customized receipt. Falls back to the standard logo when empty.',
    )
    # Html (sanitized) rather than Text: the spec allows HTML, and Odoo's
    # sanitizer strips scripts / event handlers before anything is rendered.
    company_name = fields.Html(string='Receipt Company Name', sanitize=True)
    company_details = fields.Html(string='Receipt Company Details', sanitize=True)
    show_customer_details = fields.Boolean(
        string='Show Customer Details',
        help="Print the customer's name and address on the customized receipt.",
    )
    azk_payment_receipt_preview = fields.Boolean(
        string='Receipt Preview on Payment Screen', default=True,
        help='Show the receipt, updated live, next to the payment on large screens.',
    )
    azk_logo_is_placeholder = fields.Boolean(
        compute='_compute_azk_logo_is_placeholder',
        help="Technical: the receipt logo is Odoo's default \"Your logo\" image (or empty).",
    )
    azk_auto_email_receipt = fields.Boolean(
        string='Email Receipt Automatically',
        help='After validation, email the receipt to the customer when the customer has an email address. '
             'Needs an outgoing mail server.',
    )

    @api.depends('logo')
    def _compute_azk_logo_is_placeholder(self):
        placeholder = self.env['res.company']._get_logo().content
        for config in self:
            config.azk_logo_is_placeholder = not config.logo or config.logo.content == placeholder
