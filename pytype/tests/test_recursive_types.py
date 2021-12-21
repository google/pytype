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

  def test_match_as_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Union
      X = Union[str, List['X']]
      def f(x: X):
        pass
      f('')  # ok
      f([''])  # ok
      f([['']])  # ok
      f(0)  # wrong-arg-types[e0]
      f([0])  # wrong-arg-types[e1]
      f([[0]])  # wrong-arg-types[e2]
    """)
    self.assertErrorSequences(errors, {
        "e0": ["Expected", "Union[List[X], str]", "Actual", "int"],
        "e1": ["Expected", "Union[List[X], str]", "Actual", "List[int]"],
        "e2": ["Expected", "Union[List[X], str]", "Actual", "List[List[int]]"],
    })

  def test_match_as_value(self):
    self.CheckWithErrors("""
      from typing import Any, List, Union
      X = Union[str, List['X']]
      x: X = None

      def ok(x: Union[str, List[Any]]):
        pass
      def bad(x: Union[int, List[int]]):
        pass
      ok(x)
      bad(x)  # wrong-arg-types
    """)

  def test_match_as_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set, Union
      X1 = Union[str, List['X1']]
      X2 = Union[str, List['X2']]
      Y = Union[int, Set['Y']]
      Z = Union[int, List[Y]]
      x: X1 = None

      def matches_X1(x: X1):
        pass
      def matches_X2(x: X2):
        pass
      def matches_Y(y: Y):
        pass
      def matches_Z(z: Z):
        pass
      matches_X1(x)
      matches_X2(x)  # ok because X1 and X2 are structurally equivalent
      matches_Y(x)  # wrong-arg-types[e1]
      matches_Z(x)  # wrong-arg-types[e2]
    """)
    self.assertErrorSequences(errors, {
        "e1": ["Expected", "Union[Set[Y], int]",
               "Actual", "Union[List[Union[list, str]], str]"],
        "e2": ["Expected", "Union[List[Union[Set[Y], int]], int]",
               "Actual", "Union[List[Union[list, str]], str]"],
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
