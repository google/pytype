import re
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

  def check_error(self, src, expected_line, message):
    """Check that parsing the src raises the expected error."""
    try:
      pytd.Print(parser.parse_string(textwrap.dedent(src)))
      self.fail("ParseError expected")
    except parser.ParseError as e:
      self.assertRegexpMatches(e.message, re.escape(message))
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

    # Brackets without a typename imply a tuple.
    self.check("x = ...  # type: []",
               "x = ...  # type: Tuple[]",
               prologue="from typing import Tuple")
    self.check("x = ...  # type: [int]",
               "x = ...  # type: Tuple[int]",
               prologue="from typing import Tuple")
    self.check("x = ...  # type: [int, str]",
               "x = ...  # type: Tuple[int, str]",
               prologue="from typing import Tuple")

  def test_named_tuple(self):
    # No fields.
    self.check("x = ...  # type: NamedTuple(foo, [])", """\
      from typing import Any, Tuple

      x = ...  # type: `foo`

      class `foo`(Tuple[Any, ...]):
          pass
      """)

    # Multiple fields, various trailing commas.
    expected = """\
      from typing import Tuple, Union

      x = ...  # type: `foo`

      class `foo`(Tuple[Union[int, str], ...]):
          a = ...  # type: int
          b = ...  # type: str
    """
    self.check("x = ...  # type: NamedTuple(foo, [(a, int), (b, str)])",
               expected)
    self.check("x = ...  # type: NamedTuple(foo, [(a, int), (b, str),])",
               expected)
    self.check("x = ...  # type: NamedTuple(foo, [(a, int,), (b, str),])",
               expected)

    # Dedup basename.
    self.check("""\
      x = ...  # type: NamedTuple(foo, [(a, int,)])
      y = ...  # type: NamedTuple(foo, [(b, str,)])""",
               """\
      from typing import Tuple

      x = ...  # type: `foo`
      y = ...  # type: `foo~1`

      class `foo`(Tuple[int, ...]):
          a = ...  # type: int

      class `foo~1`(Tuple[str, ...]):
          b = ...  # type: str
        """)

  def test_function_params(self):
    self.check("def foo() -> int: ...")
    self.check("def foo(x) -> int: ...")
    self.check("def foo(x: int) -> int: ...")
    self.check("def foo(x: int, y: str) -> int: ...")
    # Default values can add type information.
    self.check("def foo(x = 123) -> int: ...",
               "def foo(x: int = ...) -> int: ...")
    self.check("def foo(x = 12.3) -> int: ...",
               "def foo(x: float = ...) -> int: ...")
    self.check("def foo(x = None) -> int: ...",
               "def foo(x: None = ...) -> int: ...")
    self.check("def foo(x = xyz) -> int: ...",
               "def foo(x = ...) -> int: ...")
    self.check("def foo(x = ...) -> int: ...",
               "def foo(x = ...) -> int: ...")
    # Default of None will turn declared type into a union.
    self.check("def foo(x: str = None) -> int: ...",
               "def foo(x: Union[str, None] = ...) -> int: ...",
               prologue="from typing import Union")
    # Other defaults are ignored if a declared type is present.
    self.check("def foo(x: str = 123) -> int: ...",
               "def foo(x: str = ...) -> int: ...")

  def test_function_star_params(self):
    self.check("def foo(*, x) -> str: ...")
    self.check("def foo(x: int, *args) -> str: ...")
    self.check("def foo(x: int, *args: float) -> str: ...",
               prologue="from typing import Tuple")
    self.check("def foo(x: int, **kwargs) -> str: ...")
    self.check("def foo(x: int, **kwargs: float) -> str: ...",
               prologue="from typing import Dict")
    self.check("def foo(x: int, *args, **kwargs) -> str: ...")
    # Various illegal uses of * args.
    self.check_error("def foo(*) -> int: ...", 1,
                     "Named arguments must follow bare *")
    self.check_error("def foo(*x, *y) -> int: ...", 1,
                     "Unexpected second *")
    self.check_error("def foo(**x, *y) -> int: ...", 1,
                     "**x must be last parameter")

  def test_function_ellipsis_param(self):
    self.check("def foo(...) -> int: ...",
               "def foo(*args, **kwargs) -> int: ...")
    self.check("def foo(x: int, ...) -> int: ...",
               "def foo(x: int, *args, **kwargs) -> int: ...")
    self.check_error("def foo(..., x) -> int: ...", 1,
                     "ellipsis (...) must be last parameter")
    self.check_error("def foo(*, ...) -> int: ...", 1,
                     "ellipsis (...) not compatible with bare *")

  def test_function_decorators(self):
    # sense for methods of classes.  But this at least gives us some coverage
    # of the decorator logic.  More sensible tests can be created once classes
    # are implemented.
    self.check("""\
      @overload
      def foo() -> int: ...""",
               """\
      def foo() -> int: ...""")

    self.check("""\
      @abstractmethod
      def foo() -> int: ...""",
               """\
      def foo() -> int: ...""")

    self.check("""\
      @staticmethod
      def foo() -> int: ...""")

    self.check("""\
      @classmethod
      def foo() -> int: ...""")

    self.check_error("""\
      @property
      def foo(self) -> int""",
                     None,
                     "Module-level functions with property decorators: foo")

    self.check_error("""\
      @foo.setter
      def foo(self, x) -> int: ...""",
                     None,
                     "Module-level functions with property decorators: foo")

    self.check_error("""\
      @classmethod
      @staticmethod
      def foo() -> int: ...""",
                     3,
                     "Too many decorators for foo")

  def test_function_empty_body(self):
    self.check("def foo() -> int: ...")
    self.check("def foo() -> int",
               "def foo() -> int: ...")
    self.check("def foo() -> int: pass",
               "def foo() -> int: ...")
    self.check("""\
      def foo() -> int:
        ...""",
               """\
      def foo() -> int: ...""")
    self.check("""\
      def foo() -> int:
        pass""",
               """\
      def foo() -> int: ...""")
    self.check("""\
      def foo() -> int:
        '''doc string'''""",
               """\
      def foo() -> int: ...""")

  def test_function_body(self):
    # Mutators.
    self.check("""\
      def foo(x) -> int:
          x := int""")
    self.check_error("""\
      def foo(x) -> int:
          y := int""", 1, "No parameter named y")
    # Raise statements (currently ignored).
    self.check("""\
      def foo(x) -> int:
          raise Error""",
               """\
      def foo(x) -> int: ...""")
    self.check("""\
      def foo(x) -> int:
          raise Error()""",
               """\
      def foo(x) -> int: ...""")

  def test_function_raises(self):
    self.check("def foo() -> int raises RuntimeError: ...")
    self.check("def foo() -> int raises RuntimeError, TypeError: ...")

  def test_duplicate_names(self):
    self.check_error("""\
      def foo() -> int: ...
      foo = ... # type: int""",
                     None,
                     "Duplicate top-level identifier(s): foo")
    self.check_error("""\
      from x import foo
      def foo() -> int: ...""",
                     None,
                     "Duplicate top-level identifier(s): foo")
    # A function is allowed to appear multiple times.
    self.check("""\
      def foo(x: int) -> int: ...
      def foo(x: str) -> str: ...""")


if __name__ == "__main__":
  unittest.main()
