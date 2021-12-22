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
      x = []
      x.append(x)
      ok: X = x
      bad1: X = [0]  # annotation-type-mismatch[e]
      bad2: X = [[0]]  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "List[X]", "Assignment", "List[int]"]})

  def test_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List
      X = List['X']
      x: X = None
      ok1: List[Any] = x
      ok2: List[X] = x
      bad: List[int] = x  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "List[int]", "Assignment", "List[X]"]})

  def test_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set
      X1 = List['X1']
      X2 = List['X2']
      Bad = Set['Bad']
      x: X1 = None
      ok1: X1 = x
      ok2: X2 = x  # ok because X1 and X2 are structurally equivalent
      bad: Bad = x  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Set[Bad]", "Assignment", "List[X1]"]})

  def test_union_as_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Union
      X = Union[str, List['X']]
      ok1: X = ''
      ok2: X = ['']
      ok3: X = [['']]
      bad1: X = 0  # annotation-type-mismatch[e]
      bad2: X = [0]  # annotation-type-mismatch
      bad3: X = [[0]]  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[List[X], str]", "Assignment", "int"],
    })

  def test_union_as_value(self):
    errors = self.CheckWithErrors("""
      from typing import Any, List, Union
      X = Union[str, List['X']]
      x: X = None
      ok: Union[str, List[Any]] = x
      bad1: Union[int, List[Any]] = x  # annotation-type-mismatch[e]
      bad2: Union[str, List[int]] = x  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[int, list]",
              "Assignment", "Union[List[X], str]"]})

  def test_union_as_value_and_type(self):
    errors = self.CheckWithErrors("""
      from typing import List, Set, Union
      X1 = Union[str, List['X1']]
      X2 = Union[str, List['X2']]
      X3 = Union[int, Union[List['X3'], str]]
      Bad1 = Union[str, Set['Bad1']]
      Bad2 = Union[int, List['Bad2']]
      Bad3 = Union[int, Union[List['Bad3'], int]]
      x: X1 = None
      ok1: X1 = x
      ok2: X2 = x  # ok because X1 and X2 are structurally equivalent
      ok3: X3 = x  # ok because (the equivalent of) X1 is contained in X3
      bad1: Bad1 = x  # annotation-type-mismatch[e]
      bad2: Bad2 = x  # annotation-type-mismatch  # annotation-type-mismatch
      bad3: Bad3 = x  # annotation-type-mismatch  # annotation-type-mismatch
    """)
    self.assertErrorSequences(errors, {
        "e": ["Annotation", "Union[Set[Bad1], str]",
              "Assignment", "List[X1]",
              "In assignment", "Union[List[X1], str]"],
    })

  def test_contained_union(self):
    self.CheckWithErrors("""
      from typing import List, Union
      X = List[Union[str, List['X']]]
      Y = List[Union[int, List['Y']]]
      x: X = None
      ok: X = x
      bad: Y = x  # annotation-type-mismatch
    """)

  def test_union_no_base_case(self):
    self.CheckWithErrors("""
      from typing import Any, List, Set, Union
      X = Union[List['X'], Set['X']]
      x1: X = None
      x2 = []
      x2.append(x2)
      x3 = set()
      x3.add(x3)
      ok1: X = x1
      ok2: X = x2
      ok3: X = x3
      bad1: X = {0}  # annotation-type-mismatch
      bad2: Set[Any] = x1  # annotation-type-mismatch
    """)


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
