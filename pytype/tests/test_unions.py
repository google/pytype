"""Tests for union types."""

from pytype.tests import test_base


class UnionTest(test_base.TargetIndependentTest):
  """Tests for union types."""

  def testIfElse(self):
    ty = self.Infer("""
      def id(x):
        return x

      def f(b, x, y):
        return id(1 if b else 1.0)
    """)

    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _T0 = TypeVar("_T0")
      def id(x: _T0) ->_T0

      def f(b, x, y) -> int or float
    """)

  def testCall(self):
    ty, errors = self.InferWithErrors("""\
      def f():
        x = 42
        if __random__:
          # Should not appear in output
          x.__class__ = float
          x.__class__ = str
        return type(x)()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)
    self.assertErrorLogIs(errors, [
        (5, "not-writable", "int"),
        (6, "not-writable", "int"),
    ])


test_base.main(globals(), __name__ == "__main__")
