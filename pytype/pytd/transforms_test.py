"""Tests for transforms.py."""

import textwrap

from pytype.pytd import transforms
from pytype.pytd.parse import parser_test_base
import unittest


class TestTransforms(parser_test_base.ParserTest):
  """Tests the code in transforms.py."""

  def test_remove_mutable_list(self):
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

  def test_remove_mutable_dict(self):
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
