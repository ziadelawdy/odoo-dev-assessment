from odoo.tests import tagged

from .common import AzkTBCommon


@tagged('post_install', '-at_install')
class TestEngine(AzkTBCommon):

    def test_parity_with_native_unfiltered(self):
        ours = self._tb_values(self.report, self._options(self.report, '2017-01-01', '2017-12-31'))
        native = self._tb_values(self.native, self._options(self.native, '2017-01-01', '2017-12-31'))
        self.assertTrue(native, 'native report returned no lines')
        self.assertParity(ours, native)
