from pytype.rewrite.abstract import abstract
from pytype.rewrite.overlays import overlays

import unittest


class OverlaysTest(unittest.TestCase):

  def test_register_function(self):

    @overlays.register_function('test_mod', 'test_func')
    class TestFunc(abstract.PytdFunction):
      pass

    expected_key = ('test_mod', 'test_func')
    self.assertIn(expected_key, overlays.FUNCTIONS)
    self.assertEqual(overlays.FUNCTIONS[expected_key], TestFunc)


if __name__ == '__main__':
  unittest.main()
