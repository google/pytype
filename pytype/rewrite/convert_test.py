import sys

from pytype.rewrite.tests import test_utils

import unittest


class GetModuleGlobalsTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    module_globals = (
        self.ctx.abstract_converter.get_module_globals(sys.version_info[:2]))
    # Sanity check a random entry.
    self.assertIn('__name__', module_globals)


if __name__ == '__main__':
  unittest.main()
