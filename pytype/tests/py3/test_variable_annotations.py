"""Tests for PEP526 variable annotations."""

from pytype import file_utils
from pytype.tests import test_base


class VariableAnnotationsBasicTest(test_base.TargetPython3BasicTest):
  """Tests for PEP526 variable annotations."""

  def testPyiAnnotations(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import List
        x: int
        y: List[int]
        class A(object):
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


class VariableAnnotationsFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for PEP526 variable annotations."""

  def testInferTypes(self):
    ty = self.Infer("""
      from typing import List

      lst: List[int] = []

      x: int = 1
      y = 2

      class A(object):
        a: int = 1
        b = 2
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List

      lst: List[int]
      x: int
      y: int

      class A(object):
          a: int
          b: int
    """)

  def testIllegalAnnotations(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar, NoReturn

      T = TypeVar('T')

      a: "abc" = "1"  # name-error[e1]
      b: 123 = "2"  # invalid-annotation[e2]
      c: NoReturn = "3"  # invalid-annotation[e3]
      d: List[int] = []
      e: List[T] = []  # not-supported-yet[e4]
      f: int if __random__ else str = 123  # invalid-annotation[e5]
      h: NoReturn = None  # invalid-annotation[e6]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Name \'abc\' is not defined", "e2": r"Not a type",
        "e3": r"NoReturn is not allowed",
        "e4": r"type parameter.*variable annotation",
        "e5": r"Must be constant", "e6": r"NoReturn is not allowed"})

  def testUninitializedClassAnnotation(self):
    ty = self.Infer("""
      class Foo:
        bar: int
        def baz(self):
          return self.bar
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        bar: int
        def baz(self) -> int
    """)

  def testUninitializedModuleAnnotation(self):
    ty = self.Infer("""
      foo: int
      bar = foo
    """)
    self.assertTypesMatchPytd(ty, """
      foo: int
      bar: int
    """)

  def testOverwriteAnnotationsDict(self):
    errors = self.CheckWithErrors("""
      __annotations__ = None
      foo: int  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"None.*__setitem__"})

  def testShadowNone(self):
    ty = self.Infer("""
      v: int = None
    """)
    self.assertTypesMatchPytd(ty, """
      v: int
    """)

  def testOverwriteAnnotation(self):
    ty = self.Infer("""
      x: int
      x = ""
    """)
    self.assertTypesMatchPytd(ty, "x: str")

  def testOverwriteAnnotationInClass(self):
    ty = self.Infer("""
      class Foo:
        x: int
        x = ""
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: str
    """)

  def testClassVariableForwardReference(self):
    ty = self.Infer("""
      class A(object):
        a: 'A' = ...
        x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        a: A
        x: int
    """)

  def testCallableForwardReference(self):
    # Callable[['A']...] creates an instance of A during output generation,
    # which previously caused a crash when iterating over existing instances.
    ty = self.Infer("""
      from typing import Callable
      class A(object):
        def __init__(self, fn: Callable[['A'], bool]):
          self.fn = fn
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      class A(object):
        fn: Callable[[A], bool]
        def __init__(self, fn: Callable[[A], bool]) -> None: ...
    """)

  def testMultipleForwardReference(self):
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

  def testNonAnnotationsDict(self):
    # Regression test to make sure `x` isn't confused with `__annotations__`.
    self.Check("""
      class K(dict):
        pass
      x = K()
      y: int = 9
      x['z'] = 5
    """)

  def testFunctionLocalAnnotation(self):
    ty = self.Infer("""
      def f():
        x: int = None
        return x
    """)
    self.assertTypesMatchPytd(ty, "def f() -> int: ...")

  @test_base.skip("directors._VariableAnnotation assumes a variable annotation "
                  "starts at the beginning of the line.")
  def testMultiStatementLine(self):
    ty = self.Infer("if __random__: v: int = None")
    self.assertTypesMatchPytd(ty, "v: int")

  def testRetypeDefinedVariable(self):
    errors = self.CheckWithErrors("""
      v = 0
      v: str  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"'str' for v.*Annotating an already defined variable"})

  def testMultiLineAssignment(self):
    ty = self.Infer("""
      v: int = (
          None)
    """)
    self.assertTypesMatchPytd(ty, "v: int")

  def testComplexAssignment(self):
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


test_base.main(globals(), __name__ == "__main__")
