import sys

from pytype.rewrite import convert

import unittest


class GetModuleGlobalsTest(unittest.TestCase):

  def test_basic(self):
    module_globals = convert.get_module_globals(sys.version_info[:2])
    # Sanity check a random entry.
    self.assertIn('__name__', module_globals)


if __name__ == '__main__':
  unittest.main()
