"""Tests for union types."""

from pytype.tests import test_inference


class UnionTest(test_inference.InferenceTest):
  """Tests for union types."""

  def testIfElse(self):
    ty = self.Infer("""
      def id(x):
        return x

      def f(b, x, y):
        return id(1 if b else 1.0)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def id(x) -> Any

      def f(b, x, y) -> int or float
    """)

  def testCall(self):
    ty = self.Infer("""
      def f():
        x = 42
        if __any_object__:
          x.__class__ = float  # Should not appear in output
          x.__class__ = str
        return type(x)()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int or str
    """)


if __name__ == "__main__":
  test_inference.main()
