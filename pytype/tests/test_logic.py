"""Tests for logical constructs."""

import unittest

from pytype.tests import test_inference


class LogicTest(test_inference.InferenceTest):
  """Tests for logical constructs.

  These are tests for pieces of code that need more sophisticated understanding
  of how Python statements interact, e.g. how we can use information from one
  to decide whether we need to throw an exception in another.
  """

  @unittest.skip("Uses interaction between __hasitem__(k) and __getitem__(k)""")
  def testGetItemInLoop(self):
    # Extracted from unicode_urlparse.py:
    with self.Infer("""
      def f(args_list):
        args = dict()
        for k, v in args_list:
          if k not in args:
            args[k] = "foo"
          else:
            assert isinstance(args[k], str)
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> NoneType
      """)


if __name__ == "__main__":
  test_inference.main()
