"""Tests for union types."""

from pytype.tests import test_base
from pytype.tests import test_utils


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


@test_utils.skipBeforePy((3, 10), "New syntax in 3.10")
class UnionOrTest(test_base.BaseTest):
  """Tests for the A | B | ... type union syntax."""

  def test_basic(self):
    ty = self.Infer("""
      x: int | str
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x: Union[int, str]
    """)

  def test_chained(self):
    ty = self.Infer("""
      class A: pass
      class B: pass
      x: int | str | A | B
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x: Union[int, str, A, B]
      class A: ...
      class B: ...
    """)

  def test_none(self):
    ty = self.Infer("""
      x: int | str | None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      x: Optional[Union[int, str]]
    """)

  def test_mixed(self):
    ty = self.Infer("""
      from typing import Union
      class A: pass
      class B: pass
      x: int | str | Union[A, B]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x: Union[int, str, A, B]
      class A: ...
      class B: ...
    """)

  def test_forward_ref(self):
    ty = self.Infer("""
      from typing import Union
      class A: pass
      x: 'int | str | A | B'
      class B: pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x: Union[int, str, A, B]
      class A: ...
      class B: ...
    """)

  def test_non_type(self):
    self.Check("""
      x = __any_object__ | __any_object__
      y = __any_object__ | __any_object__
      for z in (x, y):
        pass
    """)

  def test_unsupported_late_annotation(self):
    """Don't allow partial late annotations."""
    # TODO(b/240617766): missing-parameter is the wrong error.
    self.CheckWithErrors("""
      a: int | 'str' = 0  # invalid-annotation  # missing-parameter
      b: 'Bar' | int = 0  # invalid-annotation  # unsupported-operands
      c: 'Foo' | 'Bar' = 0  # invalid-annotation  # unsupported-operands
    """)

  def test_unsupported_operands(self):
    """Don't treat assignments to | expressions as annotations."""
    # TODO(b/240617766): missing-parameter is the wrong error.
    self.CheckWithErrors("""
      a = int | 'str'  # missing-parameter
      b = 'Bar' | int  # unsupported-operands
      c = 'Foo' | 'Bar'  # unsupported-operands
    """)


if __name__ == "__main__":
  test_base.main()
