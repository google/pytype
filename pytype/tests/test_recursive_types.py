"""Tests for recursive types."""

from pytype.tests import test_base


# TODO(b/109648354): Enable --allow-recursive-types on these tests as we get
# them passing.
class RecursiveTypesTest(test_base.BaseTest):
  """Tests for recursive types."""

  def test_alias(self):
    self.options.tweak(allow_recursive_types=False)
    ty, errors = self.InferWithErrors("""
      from typing import List
      Foo = List["Foo"]  # not-supported-yet[e]
    """)
    self.assertTypesMatchPytd(ty, "from builtins import list as Foo")
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def test_use_alias_in_parameter(self):
    self.options.tweak(allow_recursive_types=False)
    errors = self.CheckWithErrors("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]  # not-supported-yet[e]
      def f(x: Foo):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def test_use_alias_in_comment(self):
    self.Check("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      x = 'hello'  # type: Foo
    """)

  def test_use_alias_in_alias(self):
    self.Check("""
      from typing import Any, Iterable, TypeVar, Union
      T = TypeVar("T")
      X = Union[Any, Iterable["X"]]
      Y = Union[Any, X]
    """)

  def test_mutually_recursive_aliases(self):
    self.options.tweak(allow_recursive_types=False)
    ty, errors = self.InferWithErrors("""
      from typing import List
      X = List["Y"]
      Y = List["X"]  # not-supported-yet[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      X = List[Y]
      Y = List[list]
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Y"})

  def test_use_unsupported_typevar(self):
    # Test that we don't crash when using this pattern (b/162274390)
    self.options.tweak(allow_recursive_types=False)
    self.CheckWithErrors("""
      from typing import List, TypeVar, Union
      T = TypeVar("T")
      Tree = Union[T, List['Tree']]  # not-supported-yet
      def f(x: Tree[int]): ... # no error since Tree is set to Any
    """)


if __name__ == "__main__":
  test_base.main()
