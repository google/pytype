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
      errors = self.CheckWithErrors("""\
        import foo
        def f(x: int) -> None:
          pass
        obj = foo.A()
        f(foo.x)
        f(foo.y)
        f(obj.a)
        f(obj.b)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [
          (6, "wrong-arg-types", r"int.*List"),
          (8, "wrong-arg-types", r"int.*str")])


class VariableAnnotationsFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for PEP526 variable annotations."""

  def testInferTypes(self):
    ty = self.Infer("""\
      from typing import List

      lst: List[int] = []

      x: int = 1
      y = 2

      class A(object):
        a: int = 1
        b = 2
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import List

      lst: List[int]
      x: int
      y: int

      class A(object):
          a: int
          b: int
    """)

  def testIllegalAnnotations(self):
    _, errors = self.InferWithErrors("""\
      from typing import List, TypeVar, NoReturn

      T = TypeVar('T')

      a: "abc" = "1"
      b: 123 = "2"
      c: NoReturn = "3"
      d: List[int] = []
      e: List[T] = []
      f: 1 if __random__ else 2 = 123
      h: NoReturn = None
    """)
    self.assertErrorLogIs(errors, [
        (5, "invalid-annotation", "Name \'abc\' is not defined"),
        (6, "invalid-annotation", "Not a type"),
        (7, "invalid-annotation", "NoReturn is not allowed"),
        (9, "not-supported-yet", r"type parameter.*variable annotation"),
        (10, "invalid-annotation", r"Type must be constant"),
        (11, "invalid-annotation", r"NoReturn is not allowed")])

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
    errors = self.CheckWithErrors("""\
      __annotations__ = None
      foo: int
    """)
    self.assertErrorLogIs(
        errors, [(2, "unsupported-operands", r"None.*__setitem__")])

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
    ty = self.Infer("""\
      class A(object):
        a: 'A' = ...
        x = 42
    """)
    self.assertTypesMatchPytd(ty, """\
      class A(object):
        a: A
        x: int
    """)


test_base.main(globals(), __name__ == "__main__")
