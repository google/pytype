"""Tests for PEP526 variable annotations."""

from pytype import file_utils
from pytype.tests import test_base


class VariableAnnotationsBasicTest(test_base.BaseTest):
  """Tests for PEP526 variable annotations."""

  def test_pyi_annotations(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        x: int
        y: List[int]
        class A:
          a: int
          b: str
      """)
      errors = self.CheckWithErrors("""
        import foo
        def f(x: int) -> None:
          pass
        obj = foo.A()
        f(foo.x)
        f(foo.y)  # wrong-arg-types[e1]
        f(obj.a)
        f(obj.b)  # wrong-arg-types[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e1": r"int.*List", "e2": r"int.*str"})


class VariableAnnotationsFeatureTest(test_base.BaseTest):
  """Tests for PEP526 variable annotations."""

  def test_infer_types(self):
    ty = self.Infer("""
      from typing import List

      lst: List[int] = []

      x: int = 1
      y = 2

      class A:
        a: int = 1
        b = 2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List

      lst: List[int]
      x: int
      y: int

      class A:
          a: int
          b: int
    """)

  def test_illegal_annotations(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar, NoReturn

      T = TypeVar('T')

      a: "abc" = "1"  # name-error[e1]
      b: 123 = "2"  # invalid-annotation[e2]
      c: NoReturn = "3"  # invalid-annotation[e3]
      d: List[int] = []
      e: List[T] = []  # invalid-annotation[e4]
      f: int if __random__ else str = 123  # invalid-annotation[e5]
      h: NoReturn = None  # invalid-annotation[e6]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Name \'abc\' is not defined", "e2": r"Not a type",
        "e3": r"NoReturn is not allowed",
        "e4": r"'T' not in scope",
        "e5": r"Must be constant", "e6": r"NoReturn is not allowed"})

  def test_uninitialized_class_annotation(self):
    ty = self.Infer("""
      class Foo:
        bar: int
        def baz(self):
          return self.bar
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        bar: int
        def baz(self) -> int: ...
    """)

  def test_uninitialized_module_annotation(self):
    ty = self.Infer("""
      foo: int
      bar = foo
    """)
    self.assertTypesMatchPytd(ty, """
      foo: int
      bar: int
    """)

  def test_overwrite_annotations_dict(self):
    errors = self.CheckWithErrors("""
      __annotations__ = None
      foo: int  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"None.*__setitem__"})

  def test_shadow_none(self):
    ty = self.Infer("""
      v: int = None
    """)
    self.assertTypesMatchPytd(ty, """
      v: int
    """)

  def test_overwrite_annotation(self):
    ty, errors = self.InferWithErrors("""
      x: int
      x = ""  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, "x: int")
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_overwrite_annotation_in_class(self):
    ty, errors = self.InferWithErrors("""
      class Foo:
        x: int
        x = ""  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: int
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_class_variable_forward_reference(self):
    ty = self.Infer("""
      class A:
        a: 'A' = ...
        x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        a: A
        x: int
    """)

  def test_callable_forward_reference(self):
    # Callable[['A']...] creates an instance of A during output generation,
    # which previously caused a crash when iterating over existing instances.
    ty = self.Infer("""
      from typing import Callable
      class A:
        def __init__(self, fn: Callable[['A'], bool]):
          self.fn = fn
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      class A:
        fn: Callable[[A], bool]
        def __init__(self, fn: Callable[[A], bool]) -> None: ...
    """)

  def test_multiple_forward_reference(self):
    ty = self.Infer("""
      from typing import Dict
      class A:
        x: Dict['A', 'B']
      class B:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      class A:
        x: Dict[A, B]
      class B: ...
    """)

  def test_non_annotations_dict(self):
    # Regression test to make sure `x` isn't confused with `__annotations__`.
    self.Check("""
      class K(dict):
        pass
      x = K()
      y: int = 9
      x['z'] = 5
    """)

  def test_function_local_annotation(self):
    ty = self.Infer("""
      def f():
        x: int = None
        return x
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int: ...")

  @test_base.skip("directors._VariableAnnotation assumes a variable annotation "
                  "starts at the beginning of the line.")
  def test_multi_statement_line(self):
    ty = self.Infer("if __random__: v: int = None")
    self.assertTypesMatchPytd(ty, "v: int")

  def test_multi_line_assignment(self):
    ty = self.Infer("""
      v: int = (
          None)
    """)
    self.assertTypesMatchPytd(ty, "v: int")

  def test_complex_assignment(self):
    # Tests that when an assignment contains multiple STORE_* opcodes on
    # different lines, we associate the annotation with the right one.
    ty = self.Infer("""
      from typing import Dict
      def f():
        column_map: Dict[str, Dict[str, bool]] = {
            column: {
                'visible': True
            } for column in __any_object__.intersection(
                __any_object__)
        }
        return column_map
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      def f() -> Dict[str, Dict[str, bool]]: ...
    """)

  def test_none_or_ellipsis_assignment(self):
    self.Check("""
      v1: int = None
      v2: str = ...
    """)

  def test_any(self):
    self.Check("""
      from typing import Any
      def f():
        x: Any = None
        print(x.upper())
        x = None
        print(x.upper())
    """)

  def test_uninitialized_variable_container_check(self):
    self.CheckWithErrors("""
      from typing import List
      x: List[str]
      x.append(0)  # container-type-mismatch
    """)

  def test_uninitialized_attribute_container_check(self):
    self.CheckWithErrors("""
      from typing import List
      class Foo:
        x: List[str]
        def __init__(self):
          self.x.append(0)  # container-type-mismatch
    """)

  def test_any_container(self):
    ty = self.Infer("""
      from typing import Any, Dict
      def f():
        x: Dict[str, Any] = {}
        x['a'] = 'b'
        for v in x.values():
          print(v.whatever)
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      def f() -> Dict[str, Any]: ...
    """)

  def test_function_parameter(self):
    self.Check("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T, y: T):
        z: T = x
        return z
      assert_type(f(0, 1), int)
    """)

  def test_illegal_parameter(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T')
      S = TypeVar('S')
      def f(x: T, y: T):
        z: S = x  # invalid-annotation[e]
        return z
    """)
    self.assertErrorRegexes(errors, {"e": r"'S' not in scope for method 'f'"})

  def test_callable_parameters(self):
    errors = self.CheckWithErrors("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      f: Callable[[T, T], T]
      assert_type(f(0, 1), int)
      f(0, '1')  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected.*int.*Actual.*str"})

  def test_nested_callable_parameters(self):
    self.Check("""
      from typing import Callable, List, TypeVar
      T = TypeVar('T')
      fs: List[Callable[[T], T]]
      assert_type(fs[0]('hello world'), str)
    """)

  def test_callable_parameters_in_method(self):
    self.Check("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      def f():
        g: Callable[[T], T] = None
        assert_type(g(0), int)
    """)

  def test_class_and_callable_parameters(self):
    errors = self.CheckWithErrors("""
      from typing import Callable, Generic, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      class Foo(Generic[T1]):
        x: Callable[[T1, T2], T2]
        def f(self):
          x: Callable[[T1, T2], T2] = None
          return x
      foo = Foo[int]()
      assert_type(foo.x(0, 'hello world'), str)
      assert_type(foo.f()(0, 4.2), float)
      foo.x(None, 'hello world')  # wrong-arg-types[e1]
      foo.f()('oops', 4.2)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Expected.*int.*Actual.*None",
                                     "e2": r"Expected.*int.*Actual.*str"})

  def test_invalid_callable_parameter(self):
    # Do not allow TypeVars that appear only once in a Callable signature.
    self.CheckWithErrors("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      f: Callable[[T], int]  # invalid-annotation
      def g(x: T, y: T):
        f2: Callable[[T], int]  # ok, since T is from the signature of g
    """)


if __name__ == "__main__":
  test_base.main()
