from pytype.rewrite.tests import test_utils
import unittest


class GetModuleGlobalsTest(test_utils.ContextfulTestBase):

  def test_basic(self):
    module_globals = self.ctx.abstract_loader.get_module_globals()
    # Sanity check a random entry.
    self.assertIn('__name__', module_globals)


if __name__ == '__main__':
  unittest.main()
