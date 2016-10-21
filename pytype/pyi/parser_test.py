import textwrap

from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd.parse import parser as legacy_parser

import unittest


class ParserTest(unittest.TestCase):

  def _check_legacy(self, src, actual):
    """Check that actual matches legacy parsing of src."""
    old_tree = legacy_parser.parse_string(src)
    self.assertMultiLineEqual(pytd.Print(old_tree), actual)

  def check(self, src, expected=None, prologue=None):
    """Check the parsing of src.

    This checks that parsing the source and then printing the resulting
    AST results in the expected text.  It also compares this to doing the
    same with the legacy parser.

    Args:
      src: A source string.
      expected: Optional expected result string.  If not provided, src is
        used instead.
      prologue: An optional prologue to be prepended to the expected text
        before comparisson.  Useful for imports that are introduced during
        printing the AST.
    """
    src = textwrap.dedent(src)
    expected = src if expected is None else textwrap.dedent(expected)
    if prologue:
      expected = "%s\n\n%s" % (textwrap.dedent(prologue), expected)
    actual = pytd.Print(parser.parse_string(src))
    self._check_legacy(src, actual)
    self.assertMultiLineEqual(expected, actual)

  def check_error(self, src, expected_line, regex):
    """Check that parsing the src raises the expected error."""
    try:
      pytd.Print(parser.parse_string(textwrap.dedent(src)))
      self.fail("ParseError expected")
    except parser.ParseError as e:
      self.assertRegexpMatches(e.message, regex)
      self.assertEquals(expected_line, e.line)

  def test_syntax_error(self):
    self.check_error("123", 1, "syntax error")

  def test_constant(self):
    self.check("x = ...", "x = ...  # type: Any", "from typing import Any")
    self.check("x = ...  # type: str")
    self.check("x = 0", "x = ...  # type: int")
    self.check_error("\nx = 123", 2,
                     "Only '0' allowed as int literal")

  def test_alias_or_constant(self):
    self.check("x = True", "x = ...  # type: bool")
    self.check("x = False", "x = ...  # type: bool")
    self.check("x = Foo")

  def test_import(self):
    self.check("import foo.bar.baz", "")
    self.check_error("\n\nimport a as b", 3,
                     "Renaming of modules not supported")
    self.check("from foo.bar import baz")
    self.check("from foo.bar import baz as abc")
    self.check("from typing import NamedTuple, TypeVar", "")
    self.check("from foo.bar import *", "")
    self.check("from foo import a, b",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b)",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b, )",
               "from foo import a\nfrom foo import b")

  def test_type(self):
    self.check("x = ...  # type: str")
    self.check("x = ...  # type: (str)", "x = ...  # type: str")
    self.check("x = ...  # type: foo.bar.Baz", prologue="import foo.bar")
    self.check("x = ...  # type: ?", "x = ...  # type: Any",
               prologue="from typing import Any")
    self.check("x = ...  # type: nothing")
    self.check("x = ...  # type: int or str or float", """\
                from typing import Union
                
                x = ...  # type: Union[int, str, float]""")

  def test_homogeneous_type(self):
    # Strip parameters from Callable.
    self.check("import typing\n\nx = ...  # type: typing.Callable[int]",
               "import typing\n\nx = ...  # type: typing.Callable")
    # B[T, ...] becomes B[T].
    self.check("x = ...  # type: List[int, ...]",
               "x = ...  # type: List[int]",
               prologue="from typing import List")
    # Double ellipsis is not allowed.
    self.check_error("x = ...  # type: List[..., ...]", 1,
                     "not supported")
    # Tuple[T] becomes Tuple[T, ...].
    self.check("from typing import Tuple\n\nx = ...  # type: Tuple[int]",
               "from typing import Tuple\n\nx = ...  # type: Tuple[int, ...]")

    # Tuple[T, U] becomes Tuple[Union[T, U]
    self.check("""\
      from typing import Tuple, Union

      x = ...  # type: Tuple[int, str]""",
               """\
      from typing import Tuple, Union

      x = ...  # type: Tuple[Union[int, str], ...]""")

    # Tuple[T, U] becomes Tuple[Union[T, U]
    self.check("""\
      from typing import Tuple, Union

      x = ...  # type: Tuple[int, str, ...]""",
               """\
      from typing import Any, Tuple, Union

      x = ...  # type: Tuple[Union[int, str, Any], ...]""")

    # Simple generic type.
    self.check("x = ...  # type: Foo[int, str]")


if __name__ == "__main__":
  unittest.main()
