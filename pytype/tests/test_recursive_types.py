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


class MatchTest(test_base.BaseTest):
  """Tests abstract matching of recursive types."""

  def test_type(self):
    errors = self.CheckWithErrors("""
      from typing import List
      X = List['X']
      def f(x: X):
        pass
      x = []
      x.append(x)
      f(x)  # ok
      f([0])  # wrong-arg-types[e]
      f([[0]])  # wrong-arg-types
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "List[X]", "Actual", "List[int]"]})

  def test_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List
      X = List['X']
      def ok1(x: List[Any]):
        pass
      def ok2(x: List[X]):
        pass
      def bad(x: List[int]):
        pass
      x: X = None
      ok1(x)
      ok2(x)
      bad(x)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "List[int]", "Actual", "List[X]"]})

  def test_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set
      X1 = List['X1']
      X2 = List['X2']
      Bad = Set['Bad']
      def matches_X1(x: X1):
        pass
      def matches_X2(x: X2):
        pass
      def matches_Bad(x: Bad):
        pass
      x: X1 = None
      matches_X1(x)
      matches_X2(x)  # ok because X1 and X2 are structurally equivalent
      matches_Bad(x)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "Set[Bad]", "Actual", "List[X1]"]})

  def test_union_as_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Union
      X = Union[str, List['X']]
      def f(x: X):
        pass
      f('')  # ok
      f([''])  # ok
      f([['']])  # ok
      f(0)  # wrong-arg-types[e]
      f([0])  # wrong-arg-types
      f([[0]])  # wrong-arg-types
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "Union[List[X], str]", "Actual", "int"],
    })

  def test_union_as_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List, Union
      X = Union[str, List['X']]
      def ok(x: Union[str, List[Any]]):
        pass
      def bad(x: Union[int, List[int]]):
        pass
      x: X = None
      ok(x)
      bad(x)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "Union[List[int], int]",
              "Actual", "Union[List[X], str]"]})

  def test_union_as_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set, Union
      X1 = Union[str, List['X1']]
      X2 = Union[str, List['X2']]
      Bad1 = Union[int, Set['Bad1']]
      Bad2 = Union[int, List[Bad1]]
      Bad3 = Union[int, List['Bad3']]
      def matches_X1(x: X1):
        pass
      def matches_X2(x: X2):
        pass
      def matches_Bad1(x: Bad1):
        pass
      def matches_Bad2(x: Bad2):
        pass
      def matches_Bad3(x: Bad3):
        pass
      x: X1 = None
      matches_X1(x)
      matches_X2(x)  # ok because X1 and X2 are structurally equivalent
      matches_Bad1(x)  # wrong-arg-types[e]
      matches_Bad2(x)  # wrong-arg-types
      matches_Bad3(x)  # TODO(b/109648354): catch this error
    """)
    self.assertErrorSequences(errors, {
        "e": ["Expected", "Union[Set[Bad1], int]",
              "Actual", "Union[List[X1], str]"],
    })


class InferenceTest(test_base.BaseTest):
  """Tests inference of recursive types."""

  def test_basic(self):
    ty = self.Infer("""
      from typing import List
      Foo = List["Foo"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      Foo = List[Foo]
    """)

  def test_mutual_recursion(self):
    ty = self.Infer("""
      from typing import List
      X = List["Y"]
      Y = List["X"]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      X = List[Y]
      Y = List[List[Y]]
    """)

  def test_parameterization(self):
    ty = self.Infer("""
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = List["Y[int]"]
      Y = Union[T, List["Y"]]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar, Union
      T = TypeVar('T')
      X = List[Y[int]]
      Y = Union[T, List[Y]]
    """)


# TODO(b/109648354): also test:
# - reingesting mutually recursive types
# - reingesting parameterized recursive types
# - pickling
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

  @test_base.skip("TODO(b/109648354): implement")
  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing import List, Union
      X = Union[int, List['X']]
    """)]):
      ty = self.Infer("""
        import foo
        X = foo.X
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, Union
      X = Union[int, List[X]]
    """)


if __name__ == "__main__":
  test_base.main()
