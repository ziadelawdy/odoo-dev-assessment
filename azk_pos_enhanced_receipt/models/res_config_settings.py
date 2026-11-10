from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_use_customized_receipt = fields.Boolean(related='pos_config_id.use_customized_receipt', readonly=False)
    pos_receipt_logo = fields.Image(related='pos_config_id.receipt_logo', readonly=False)
    pos_company_name = fields.Html(related='pos_config_id.company_name', readonly=False)
    pos_company_details = fields.Html(related='pos_config_id.company_details', readonly=False)
    pos_show_customer_details = fields.Boolean(related='pos_config_id.show_customer_details', readonly=False)
    pos_azk_payment_receipt_preview = fields.Boolean(related='pos_config_id.azk_payment_receipt_preview', readonly=False)
    pos_azk_auto_email_receipt = fields.Boolean(related='pos_config_id.azk_auto_email_receipt', readonly=False)
