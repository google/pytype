"""Tests for transforms.py."""

import textwrap

from pytype.pytd import transforms
from pytype.pytd import visitors
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser_test_base
import unittest


class TestTransforms(parser_test_base.ParserTest):
  """Tests the code in transforms.py."""

  def ParseWithLookup(self, src):
    tree = self.Parse(src)
    return visitors.LookupClasses(tree, builtins.GetBuiltinsPyTD(
        self.PYTHON_VERSION))

  def testPreprocessReverseOperatorsVisitor(self):
    src1 = textwrap.dedent("""
      class A():
        def __add__(self, other: B) -> int
        def __rdiv__(self, other: A) -> float
        def __rmod__(self, other: B) -> str
      class B():
        def __radd__(self, other: A) -> complex  # ignored
        def __rmul__(self, other: A) -> complex
    """)
    src2 = textwrap.dedent("""
      class A():
        def __add__(self, other: B) -> int
        def __div__(self, other: A) -> float
        def __mul__(self, other: B) -> complex
      class B():
        def __mod__(self, other: A) -> str
    """)
    tree = self.ParseWithLookup(src1)
    tree = tree.Visit(transforms.PreprocessReverseOperatorsVisitor())
    self.AssertSourceEquals(tree, src2)

  def testReverseOperatorsWithInheritance(self):
    src1 = textwrap.dedent("""
      class A(object):
        def __add__(self, other: B) -> int
        def __add__(self, other: C) -> bool
        def __rdiv__(self, other: A) -> complex
      class B(object):
        def __radd__(self, other: A) -> str
        def __rmul__(self, other: A) -> float
      class C(A):
        def __add__(self, other: A) -> bool
        def __radd__(self, other: A) -> float
        def __rmul__(self, other: A) -> float
    """)
    src2 = textwrap.dedent("""
      class A(object):
        def __add__(self, other: B) -> int  # unchanged
        def __add__(self, other: C) -> float  # overwritten
        def __div__(self, other: A) -> complex  # added, __rdiv__ removed
        def __mul__(self, other: B) -> float  # added, __rmul__ from B
        def __mul__(self, other: C) -> float  # added, __rmul__ from C
      class B(object):
        pass
      class C(A):
        def __add__(self, other: A) -> bool
    """)
    tree = self.ParseWithLookup(src1)
    tree = tree.Visit(transforms.PreprocessReverseOperatorsVisitor())
    self.AssertSourceEquals(tree, src2)

  def testRemoveMutableList(self):
    # Simple test for RemoveMutableParameters, with simplified list class
    src = textwrap.dedent("""
      T = TypeVar('T')
      T2 = TypeVar('T2')

      class TrivialList(typing.Generic[T], object):
        def append(self, v: T2) -> NoneType:
          self = T or T2

      class TrivialList2(typing.Generic[T], object):
        def __init__(self, x: T) -> NoneType
        def append(self, v: T2) -> NoneType:
          self = T or T2
        def get_first(self) -> T
    """)
    expected = textwrap.dedent("""
      T = TypeVar('T')
      T2 = TypeVar('T2')

      class TrivialList(typing.Generic[T], object):
          def append(self, v: T) -> NoneType

      class TrivialList2(typing.Generic[T], object):
          def __init__(self, x: T) -> NoneType
          def append(self, v: T) -> NoneType
          def get_first(self) -> T
    """)
    ast = self.Parse(src)
    ast = transforms.RemoveMutableParameters(ast)
    self.AssertSourceEquals(ast, expected)

  def testRemoveMutableDict(self):
    # Test for RemoveMutableParameters, with simplified dict class.
    src = textwrap.dedent("""
      K = TypeVar('K')
      V = TypeVar('V')
      T = TypeVar('T')
      K2 = TypeVar('K2')
      V2 = TypeVar('V2')

      class MyDict(typing.Generic[K, V], object):
          def getitem(self, k: K, default: T) -> V or T
          def setitem(self, k: K2, value: V2) -> NoneType:
              self = dict[K or K2, V or V2]
          def getanykeyorvalue(self) -> K or V
          def setdefault(self, k: K2, v: V2) -> V or V2:
              self = dict[K or K2, V or V2]
    """)
    expected = textwrap.dedent("""
      K = TypeVar('K')
      V = TypeVar('V')
      T = TypeVar('T')
      K2 = TypeVar('K2')
      V2 = TypeVar('V2')

      class MyDict(typing.Generic[K, V], object):
          def getitem(self, k: K, default: V) -> V
          def setitem(self, k: K, value: V) -> NoneType
          def getanykeyorvalue(self) -> K or V
          def setdefault(self, k: K, v: V) -> V
    """)
    ast = self.Parse(src)
    ast = transforms.RemoveMutableParameters(ast)
    self.AssertSourceEquals(ast, expected)


if __name__ == "__main__":
  unittest.main()
