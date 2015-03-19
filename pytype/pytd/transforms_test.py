"""Tests for transforms.py."""

import textwrap


from pytype.pytd import transforms
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser_test
from pytype.pytd.parse import visitors
import unittest


class TestTransforms(parser_test.ParserTest):
  """Tests the code in transforms.py."""

  def ParseWithLookup(self, src):
    tree = self.Parse(src)
    return visitors.LookupClasses(
        tree, visitors.LookupClasses(builtins.GetBuiltinsPyTD()))

  def testPreprocessReverseOperatorsVisitor(self):
    src1 = textwrap.dedent("""
      class A(nothing):
        def __add__(self, other: B) -> int
        def __rdiv__(self, other: A) -> float
        def __rmod__(self, other: B) -> str
      class B(nothing):
        def __radd__(self, other: A) -> complex  # ignored
        def __rmul__(self, other: A) -> complex
    """)
    src2 = textwrap.dedent("""
      class A(nothing):
        def __add__(self, other: B) -> int
        def __div__(self, other: A) -> float
        def __mul__(self, other: B) -> complex
      class B(nothing):
        def __mod__(self, other: A) -> str
    """)
    tree = self.ParseWithLookup(src1)
    tree = tree.Visit(transforms.PreprocessReverseOperatorsVisitor())
    self.AssertSourceEquals(tree, src2)

  def testReverseOperatorsWithInheritance(self):
    src1 = textwrap.dedent("""
      class A:
        def __add__(self, other: B) -> int
        def __add__(self, other: C) -> bool
        def __rdiv__(self, other: A) -> complex
      class B:
        def __radd__(self, other: A) -> str
        def __rmul__(self, other: A) -> float
      class C(A):
        def __add__(self, other: A) -> bool
        def __radd__(self, other: A) -> float
        def __rmul__(self, other: A) -> float
    """)
    src2 = textwrap.dedent("""
      class A:
        def __add__(self, other: B) -> int  # unchanged
        def __add__(self, other: C) -> float  # overwritten
        def __div__(self, other: A) -> complex  # added, __rdiv__ removed
        def __mul__(self, other: B) -> float  # added, __rmul__ from B
        def __mul__(self, other: C) -> float  # added, __rmul__ from C
      class B:
        pass
      class C(A):
        def __add__(self, other: A) -> bool
    """)
    tree = self.ParseWithLookup(src1)
    tree = tree.Visit(transforms.PreprocessReverseOperatorsVisitor())
    self.AssertSourceEquals(tree, src2)


if __name__ == "__main__":
  unittest.main()
