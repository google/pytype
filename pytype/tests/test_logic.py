"""Tests for logical constructs."""

from pytype.tests import test_inference


class LogicTest(test_inference.InferenceTest):
  """Tests for logical constructs.

  These are tests for pieces of code that need more sophisticated understanding
  of how Python statements interact, e.g. how we can use information from one
  to decide whether we need to throw an exception in another.
  """

  def testGetItemInLoop(self):
    # Extracted from unicode_urlparse.py:
    ty = self.Infer("""
      def f(args_list):
        args = dict()
        for k, v in args_list:
          if k not in args:
            args[k] = "foo"
          else:
            assert isinstance(args[k], str)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      def f(args_list) -> NoneType
    """)


if __name__ == "__main__":
  test_inference.main()
