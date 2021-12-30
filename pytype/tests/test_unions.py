"""Tests for union types."""

from pytype.tests import test_base


class UnionTest(test_base.BaseTest):
  """Tests for union types."""

  def test_if_else(self):
    ty = self.Infer("""
      def id(x):
        return x

      def f(b, x, y):
        return id(1 if b else 1.0)
    """)

    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar, Union
      _T0 = TypeVar("_T0")
      def id(x: _T0) ->_T0: ...

      def f(b, x, y) -> Union[int, float]: ...
    """)

  def test_call(self):
    ty, errors = self.InferWithErrors("""
      def f():
        x = 42
        if __random__:
          # Should not appear in output
          x.__class__ = float  # not-writable[e1]
          x.__class__ = str  # not-writable[e2]
        return type(x)()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)
    self.assertErrorRegexes(errors, {"e1": r"int", "e2": r"int"})

  def test_bad_forward_reference(self):
    self.CheckWithErrors("""
      from typing import Union
      X = Union[str, 'DoesNotExist']  # name-error
    """)

  def test_parameterization(self):
    ty = self.Infer("""
      from typing import Optional, Union, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Union[int, T1]
      Y = X[Optional[T2]]
      Z = Y[str]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Union[int, T1]
      Y = Union[int, Optional[T2]]
      Z = Union[int, Optional[str]]
    """)


if __name__ == "__main__":
  test_base.main()
