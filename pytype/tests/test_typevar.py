"""Tests for TypeVar."""

import os
import unittest

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
      List = ...  # type: type
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: typing.List[T]) -> T: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  @unittest.skip("Module._convert_member needs to learn about type parameters.")
  def testAnyStr(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import AnyStr
      def f(x: AnyStr) -> AnyStr: ...
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import AnyStr
      def f(x: AnyStr) -> AnyStr: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)


if __name__ == "__main__":
  test_inference.main()
