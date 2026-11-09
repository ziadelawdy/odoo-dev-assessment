import io
from unittest.mock import patch

from openpyxl import load_workbook

from odoo.tests import tagged

from .common import AzkTBCommon

SECTION_ORDER = ('initial_balance', 'period', 'end_balance')
LABEL_ORDER = ('debit', 'credit', 'balance')


@tagged('post_install', '-at_install')
class TestExports(AzkTBCommon):

    def _filtered_options(self, journals=(), **azk_tb):
        extra = {'journals': [{'id': j, 'selected': True} for j in journals]} if journals else {}
        return self._options(self.report, '2017-01-01', '2017-12-31', azk_tb=azk_tb, **extra)

    def _xlsx_sheet(self, options):
        content = self.report.export_to_xlsx(options)['file_content']
        return load_workbook(io.BytesIO(content)).worksheets[0]

    @staticmethod
    def _header_text(sheet, rows=8):
        return ' '.join(
            str(value) for row in sheet.iter_rows(min_row=1, max_row=rows, values_only=True)
            for value in row if value is not None
        )

    def test_xlsx_header(self):
        sale = self.company_data['default_journal_sale']
        sheet = self._xlsx_sheet(self._filtered_options(journals=[sale.id]))
        header = self._header_text(sheet)
        self.assertIn(self.company_data['company'].name, header)
        self.assertIn('2017-01-01', header)
        self.assertIn('2017-12-31', header)
        self.assertIn(sale.name, header)

    def test_xlsx_values_match_report(self):
        options = self._filtered_options()
        values = self._tb_values(self.report, options)
        sheet = self._xlsx_sheet(options)
        accounts = {
            self.company_data[key] for key in
            ('default_account_receivable', 'default_account_payable', 'default_account_revenue')
        }
        checked = 0
        for row in sheet.iter_rows(values_only=True):
            label = next((v for v in row if isinstance(v, str)), '')
            account = next((a for a in accounts if label.startswith(a.code)), None)
            if not account:
                continue
            numbers = [v for v in row if not isinstance(v, str) and v is not None]
            self.assertEqual(len(numbers), 9, f'{label}: numeric cells {row}')
            expected = [
                values[account.id]['_sections'][section][label_key]
                for section in SECTION_ORDER for label_key in LABEL_ORDER
            ]
            for got, want in zip(numbers, expected):
                self.assertIsInstance(got, (int, float))
                self.assertAlmostEqual(got, want, places=2, msg=label)
            checked += 1
        self.assertEqual(checked, len(accounts))

    def test_xlsx_total_row_bold(self):
        sheet = self._xlsx_sheet(self._filtered_options())
        total_cells = [row[0] for row in sheet.iter_rows() if any(c.value == 'Total' for c in row)]
        self.assertTrue(total_cells)
        total_row = next(row for row in sheet.iter_rows() if any(c.value == 'Total' for c in row))
        self.assertTrue(any(c.font.b for c in total_row if isinstance(c.value, (int, float))))

    def test_xlsx_analytic_notice(self):
        plan = self.env['account.analytic.plan'].create({'name': 'Export Plan'})
        analytic = self.env['account.analytic.account'].create({'name': 'Export Dept', 'plan_id': plan.id})
        header = self._header_text(self._xlsx_sheet(self._filtered_options(analytic_account_ids=[analytic.id])))
        self.assertIn('not balanced', header)
        self.assertIn('Export Dept', header)

    def test_pdf_header_contains_filters(self):
        sale = self.company_data['default_journal_sale']
        options = self._filtered_options(journals=[sale.id], account_prefixes=['1'])
        lines = self.report._get_lines(options)
        html = str(self.report._get_pdf_export_html(options, lines))
        self.assertIn(self.company_data['company'].name, html)
        self.assertIn('2017-01-01', html)
        self.assertIn('2017-12-31', html)
        self.assertIn(sale.name, html)
        self.assertIn('Account prefixes: 1', html)

    def test_pdf_generates(self):
        """export_to_pdf renders our header and lines and hands them to wkhtmltopdf.

        wkhtmltopdf itself is stubbed: inside a test transaction it would fetch
        the PDF stylesheet from this same (blocked) Odoo process and deadlock.
        The real PDF is checked manually with a running server (README)."""
        captured = {}

        def fake_pdf_engine(_self, engine_name, bodies, **kwargs):
            captured['bodies'] = bodies
            return b'%PDF-1.4 stub'

        sale = self.company_data['default_journal_sale']
        report_model = type(self.env['ir.actions.report'])
        with patch.object(report_model, '_run_pdf_engine_without_processing', fake_pdf_engine):
            result = self.report.export_to_pdf(self._filtered_options(journals=[sale.id]))

        self.assertEqual(result['file_type'], 'pdf')
        self.assertTrue(result['file_content'].startswith(b'%PDF'))
        html = ''.join(str(body) for body in captured['bodies'])
        self.assertIn(self.company_data['company'].name, html)
        self.assertIn('2017-01-01', html)
        self.assertIn(sale.name, html)
        self.assertIn(self.company_data['default_account_receivable'].code, html)

    def test_wizard_export_actions(self):
        wizard = self.env['azk.dynamic.trial.balance.wizard'].create({'date_from': '2017-01-01', 'date_to': '2017-12-31'})
        for method, generator in (('action_pdf', 'export_to_pdf'), ('action_xlsx', 'export_to_xlsx')):
            action = getattr(wizard, method)()
            self.assertEqual(action['type'], 'ir_actions_account_report_download')
            self.assertEqual(action['data']['file_generator'], generator)
