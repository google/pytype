"""Tests for recursive types."""

from pytype import file_utils
from pytype.tests import test_base


class UsageTest(test_base.BaseTest):
  """Tests usage of recursive types in source code."""

  def test_parameter(self):
    self.Check("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      def f(x: Foo):
        pass
    """)

  def test_comment(self):
    self.Check("""
      from typing import List, Union
      Foo = Union[str, List['Foo']]
      x = 'hello'  # type: Foo
    """)

  def test_alias(self):
    self.Check("""
      from typing import Any, Iterable, TypeVar, Union
      T = TypeVar("T")
      X = Union[Any, Iterable["X"]]
      Y = Union[Any, X]
    """)

  def test_generic_alias(self):
    self.Check("""
      from typing import List, TypeVar, Union
      T = TypeVar("T")
      Tree = Union[T, List['Tree']]
      def f(x: Tree[int]): ...
    """)


# TODO(b/109648354): Enable --allow-recursive-types on these tests as we get
# them passing.
class InferenceTest(test_base.BaseTest):
  """Tests inference of recursive types."""

  def test_basic(self):
    self.options.tweak(allow_recursive_types=False)
    ty, errors = self.InferWithErrors("""
      from typing import List
      Foo = List["Foo"]  # not-supported-yet[e]
    """)
    self.assertTypesMatchPytd(ty, "from builtins import list as Foo")
    self.assertErrorRegexes(errors, {"e": r"Recursive.*Foo"})

  def test_mutual_recursion(self):
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


class PyiTest(test_base.BaseTest):
  """Tests recursive types defined in pyi files."""

  def test_basic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        X = List[X]
      """)
      self.Check("""
        import foo
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
