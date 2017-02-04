"""Tests for TypeVar."""


from pytype import utils
from pytype.tests import test_inference


class TypeVarTest(test_inference.InferenceTest):
  """Tests for TypeVar."""

  def testId(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      import typing
      T = typing.TypeVar("T")  # pytype: disable=not-supported-yet
      def f(x: T) -> T: ...
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      typing = ...  # type: module
      T = TypeVar("T")
      def f(x: T) -> T: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testExtractItem(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, TypeVar  # pytype: disable=not-supported-yet
      S = TypeVar("S")  # unused
      T = TypeVar("T")
      def f(x: List[T]) -> T: ...
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: typing.List[T]) -> T: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testAnyStr(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import AnyStr  # pytype: disable=not-supported-yet
      def f(x: AnyStr) -> AnyStr: ...
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      AnyStr = TypeVar("AnyStr")
      def f(x: AnyStr) -> AnyStr: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testAnyStrFunctionImport(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        from a import f
      """, deep=True, solve_unknowns=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        AnyStr = TypeVar('AnyStr')
        def f(x: AnyStr) -> AnyStr
      """)

  def testUnusedTypeVar(self):
    ty = self.Infer("""
      from typing import TypeVar  # pytype: disable=not-supported-yet
      T = TypeVar("T")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      T = TypeVar("T")
    """)


if __name__ == "__main__":
  test_inference.main()
