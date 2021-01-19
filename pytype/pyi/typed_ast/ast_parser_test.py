"""Tests for parse_ast.py."""

import sys
import textwrap

from pytype.pyi.typed_ast import ast_parser
from pytype.pyi.typed_ast.types import ParseError  # pylint: disable=g-importing-member
from pytype.pytd import pytd
from pytype.tests import test_base

import unittest


class ErrorTest(test_base.UnitTest):
  """Test parser errors."""

  def test_filename(self):
    src = textwrap.dedent("""
      a: int
      a: int
    """)
    with self.assertRaisesRegex(ParseError, "File.*foo.pyi"):
      ast_parser.parse_pyi(src, "foo.pyi", "foo", (3, 6))

  def test_lineno(self):
    src = textwrap.dedent("""
      class A:
        __slots__ = 0
    """)
    with self.assertRaisesRegex(ParseError, "line 3"):
      ast_parser.parse_pyi(src, "foo.py", "foo", (3, 6))


class ConditionTest(test_base.UnitTest):
  """Test if conditions."""

  def test_basic(self):
    src = textwrap.dedent("""
      if sys.version_info[:2] >= (3, 9) and sys.platform == 'linux':
        a: int
      elif sys.version_info[0] == 3:
        a: bool
      else:
        a: str
    """)
    root = ast_parser.parse_pyi(src, "foo.py", "foo", (3, 6))
    self.assertCountEqual(root.constants, (
        pytd.Constant("foo.a", pytd.NamedType("bool")),
    ))


class ParamsTest(test_base.UnitTest):
  """Test input parameter handling."""

  def test_feature_version(self):
    cases = [
        [2, 6],
        [(2,), 6],
        [(2, 7), 6],
        [(2, 7, 8), 6],
        [3, sys.version_info.minor],
        [(3,), sys.version_info.minor],
        [(3, 7), 7],
        [(3, 8, 2), 8]
    ]
    for version, expected in cases:
      actual = ast_parser._feature_version(version)
      self.assertEqual(actual, expected)


if __name__ == "__main__":
  unittest.main()
