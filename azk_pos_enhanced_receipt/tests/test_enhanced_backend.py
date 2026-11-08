from odoo.tests import TransactionCase, tagged

FIELDS = ('use_customized_receipt', 'receipt_logo', 'company_name', 'company_details', 'show_customer_details')


@tagged('post_install', '-at_install')
class TestEnhancedBackend(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Enhanced Receipt Test'})

    def test_fields_exist_and_defaults(self):
        for name in FIELDS:
            self.assertIn(name, self.config._fields, name)
        self.assertFalse(self.config.use_customized_receipt)
        self.assertFalse(self.config.show_customer_details)
        self.assertEqual(self.config._fields['company_name'].type, 'html')
        self.assertEqual(self.config._fields['company_details'].type, 'html')

    def test_company_html_sanitized(self):
        dirty = '<b>NOX</b><script>alert(1)</script><img src="x" onerror="alert(1)">'
        self.config.write({'company_name': dirty, 'company_details': dirty})
        for name in ('company_name', 'company_details'):
            value = str(self.config[name])
            self.assertIn('<b>NOX</b>', value, name)
            self.assertNotIn('<script', value, name)
            self.assertNotIn('onerror', value, name)

    def test_views_expose_fields(self):
        config_form = self.env['pos.config'].get_views([(False, 'form')])['views']['form']['arch']
        settings_form = self.env['res.config.settings'].get_views([(False, 'form')])['views']['form']['arch']
        for name in FIELDS:
            self.assertIn(f'name="{name}"', config_form, name)
            self.assertIn(f'name="pos_{name}"', settings_form, name)

    def test_settings_write_through(self):
        settings = self.env['res.config.settings'].create({
            'pos_config_id': self.config.id,
            'pos_use_customized_receipt': True,
            'pos_show_customer_details': True,
            'pos_company_name': '<p>NOX Trading</p>',
        })
        settings.execute()
        self.assertTrue(self.config.use_customized_receipt)
        self.assertTrue(self.config.show_customer_details)
        self.assertIn('NOX Trading', str(self.config.company_name))

    def test_no_native_field_clash(self):
        for name in FIELDS:
            field = self.env['ir.model.fields']._get('pos.config', name)
            self.assertIn('azk_pos_enhanced_receipt', field.modules, name)
