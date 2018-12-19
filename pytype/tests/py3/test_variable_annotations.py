"""Tests for PEP526 variable annotations."""

from pytype import file_utils
from pytype.tests import test_base
from pytype.tests import test_utils


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

  @test_utils.skipInVersion(
      (3, 7), "https://github.com/google/pytype/issues/216")
  def testInferTypes(self):
    ty = self.Infer("""\
      from typing import List

      lst: List[int] = []
      captain: str  # Note: no initial value!

      x : int = 1
      y = 2

      class A(object):
        a: int = 1
        b: int = 2
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

  @test_utils.skipInVersion(
      (3, 7), "https://github.com/google/pytype/issues/216")
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


test_base.main(globals(), __name__ == "__main__")
