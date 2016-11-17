import gc
import hashlib
import os
import re
import sys
import textwrap

from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd.parse import parser as legacy_parser

import unittest

IGNORE = object()


def get_builtins_source():
  pytd_dir = os.path.dirname(os.path.dirname(legacy_parser.__file__))
  with open(os.path.join(pytd_dir, "builtins/__builtin__.pytd")) as f:
    return f.read()


class _ParserTestBase(unittest.TestCase):

  def _check_legacy(self, src, name, actual):
    """Check that actual matches legacy parsing of src."""
    old_tree = legacy_parser.parse_string(src, name=name)
    self.assertMultiLineEqual(pytd.Print(old_tree), actual)

  def check(self, src, expected=None, prologue=None, legacy=True, name=None):
    """Check the parsing of src.

    This checks that parsing the source and then printing the resulting
    AST results in the expected text.  It also compares this to doing the
    same with the legacy parser.

    Args:
      src: A source string.
      expected: Optional expected result string.  If not provided, src is
        used instead.  The special value IGNORE can be used to skip
        checking the parsed results against expected text.
      prologue: An optional prologue to be prepended to the expected text
        before comparisson.  Useful for imports that are introduced during
        printing the AST.
      legacy: If true, comapre results to legacy parser.
      name: The name of the module.

    Returns:
      The parsed pytd.TypeDeclUnit.
    """
    src = textwrap.dedent(src)
    ast = parser.parse_string(src, name=name)
    actual = pytd.Print(ast)
    if legacy:
      self._check_legacy(src, name, actual)
    if expected != IGNORE:
      expected = src if expected is None else textwrap.dedent(expected)
      if prologue:
        expected = "%s\n\n%s" % (textwrap.dedent(prologue), expected)
      self.assertMultiLineEqual(expected, actual)
    return ast

  def check_error(self, src, expected_line, message):
    """Check that parsing the src raises the expected error."""
    try:
      parser.parse_string(textwrap.dedent(src))
      self.fail("ParseError expected")
    except parser.ParseError as e:
      self.assertRegexpMatches(e.message, re.escape(message))
      self.assertEquals(expected_line, e.line)


class ParseErrorTest(unittest.TestCase):

  def check(self, expected, *args, **kwargs):
    e = parser.ParseError(*args, **kwargs)
    self.assertMultiLineEqual(textwrap.dedent(expected), str(e))

  def test_plain_error(self):
    self.check("""\
        ParseError: my message""", "my message")

  def test_full_error(self):
    self.check("""\
          File: "foo.py", line 123
            this is a test
                 ^
        ParseError: my message""", "my message", line=123, filename="foo.py",
               text="this is a test", column=6)

  def test_indented_text(self):
    self.check("""\
          File: "foo.py", line 123
            this is a test
                 ^
        ParseError: my message""", "my message", line=123, filename="foo.py",
               text="          this is a test", column=16)

  def test_line_without_filename(self):
    self.check("""\
          File: "None", line 1
        ParseError: my message""", "my message", line=1)

  def test_filename_without_line(self):
    self.check("""\
          File: "foo.py", line None
        ParseError: my message""", "my message", filename="foo.py")

  def test_text_without_column(self):
    self.check("""\
        ParseError: my message""", "my message", text="this is  a test")

  def test_column_without_text(self):
    self.check("""\
        ParseError: my message""", "my message", column=5)


class ParserTest(_ParserTestBase):

  def test_syntax_error(self):
    self.check_error("123", 1, "syntax error")

  def test_illegal_character(self):
    self.check_error("^", 1, "Illegal character '^'")

  def test_invalid_indentation(self):
    self.check_error("""\
      class Foo:
        x = ... # type: int
       y""", 3, "Invalid indentation")

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
    self.check_error("""\
      X = ... # type: int
      class X: ...""",
                     None,
                     "Duplicate top-level identifier(s): X")
    self.check_error("""\
      X = ... # type: int
      X = TypeVar('X')""",
                     None,
                     "Duplicate top-level identifier(s): X")
    # A function is allowed to appear multiple times.
    self.check("""\
      def foo(x: int) -> int: ...
      def foo(x: str) -> str: ...""")

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

  def test_alias_lookup(self):
    self.check("""\
      from somewhere import Foo
      x = ...  # type: Foo
      """, """\
      import somewhere
      
      from somewhere import Foo
      
      x = ...  # type: somewhere.Foo""")

  def test_type_params(self):
    ast = self.check("""\
      from typing import TypeVar

      T = TypeVar('T')

      def func(x: T) -> T: ...""")
    # During parsing references to type paraemters are instances of NamedType.
    # They should be replaced by TypeParameter objects during post-processing.
    sig = ast.functions[0].signatures[0]
    self.assertIsInstance(sig.params[0].type, pytd.TypeParameter)
    self.assertIsInstance(sig.return_type, pytd.TypeParameter)

    # Check various illegal TypeVar arguments that are caught by semantic
    # checking rather than the grammar.
    self.check_error("T = TypeVar()", 1,
                     "TypeVar's first arg should be a string")
    self.check_error("T = TypeVar(*args)", 1,
                     "TypeVar's first arg should be a string")
    self.check_error("T = TypeVar(...)", 1,
                     "TypeVar's first arg should be a string")
    self.check_error("T = TypeVar('Q')", 1,
                     "TypeVar name needs to be 'Q' (not 'T')")

  def test_error_formatting(self):
    src = """\
      class Foo:
        this is not valid"""
    try:
      parser.parse_string(textwrap.dedent(src), filename="foo.py")
      self.fail("ParseError expected")
    except parser.ParseError as e:
      self.assertMultiLineEqual(textwrap.dedent("""\
          File: "foo.py", line 2
            this is not valid
                 ^
        ParseError: syntax error, unexpected NAME, expecting '='"""), str(e))

  def test_pep484_translations(self):
    ast = self.check("""\
      x = ...  # type: None
      y = ...  # type: Any""", prologue="from typing import Any")
    self.assertEquals(pytd.NamedType("NoneType"), ast.constants[0].type)
    self.assertEquals(pytd.AnythingType(), ast.constants[1].type)

  def test_module_name(self):
    ast = self.check("x = ...  # type: int",
                     "foo.x = ...  # type: int",
                     name="foo")
    self.assertEquals("foo", ast.name)

  def test_no_module_name(self):
    # If the name is not specified, it is a digest of the source.
    src = ""
    ast = self.check(src)
    self.assertEquals(hashlib.md5(src).hexdigest(), ast.name)
    src = "x = ...  # type: int"
    ast = self.check(src)
    self.assertEquals(hashlib.md5(src).hexdigest(), ast.name)

  def test_pep84_aliasing(self):
    # Normally a pep484 name will be converted to typing.X.  Note that this
    # test cannot use type with an upper/lower case conversion (i.e. List)
    # because those appear to be replaced regardless of the contents of the
    # parser's _type_map.
    self.check("x = ... # type: Hashable",
               "foo.x = ...  # type: typing.Hashable",
               prologue="import typing",
               name="foo")
    # This should not be done for the typing module itself.
    self.check("x = ... # type: Hashable",
               "typing.x = ...  # type: Hashable",
               name="typing")


class HomogeneousTypeTest(_ParserTestBase):

  def test_strip_callable_parameters(self):
    self.check("import typing\n\nx = ...  # type: typing.Callable[int]",
               "import typing\n\nx = ...  # type: typing.Callable")

  def test_ellipsis(self):
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

  def test_tuple(self):
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

  def test_simple(self):
    self.check("x = ...  # type: Foo[int, str]")

  def test_implied_tuple(self):
    self.check("x = ...  # type: []",
               "x = ...  # type: Tuple[]",
               prologue="from typing import Tuple")
    self.check("x = ...  # type: [int]",
               "x = ...  # type: Tuple[int]",
               prologue="from typing import Tuple")
    self.check("x = ...  # type: [int, str]",
               "x = ...  # type: Tuple[int, str]",
               prologue="from typing import Tuple")


class NamedTupleTest(_ParserTestBase):

  def test_no_fields(self):
    self.check("x = ...  # type: NamedTuple(foo, [])", """\
      from typing import Any, Tuple

      x = ...  # type: `foo`

      class `foo`(Tuple[Any, ...]):
          pass
      """)

  def test_multiple_fields(self):
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

  def test_dedup_basename(self):
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


class FunctionTest(_ParserTestBase):

  def test_params(self):
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

  def test_star_params(self):
    self.check("def foo(*, x) -> str: ...")
    self.check("def foo(x: int, *args) -> str: ...")
    self.check("def foo(x: int, *args, key: int = ...) -> str: ...")
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

  def test_ellipsis_param(self):
    self.check("def foo(...) -> int: ...",
               "def foo(*args, **kwargs) -> int: ...")
    self.check("def foo(x: int, ...) -> int: ...",
               "def foo(x: int, *args, **kwargs) -> int: ...")
    self.check_error("def foo(..., x) -> int: ...", 1,
                     "ellipsis (...) must be last parameter")
    self.check_error("def foo(*, ...) -> int: ...", 1,
                     "ellipsis (...) not compatible with bare *")

  def test_decorators(self):
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

  def test_empty_body(self):
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

  def test_body(self):
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

  def test_return(self):
    self.check("def foo() -> int: ...")
    self.check("def foo(): ...",
               "def foo() -> Any: ...",
               prologue="from typing import Any")

  def test_raises(self):
    self.check("def foo() -> int raises RuntimeError: ...")
    self.check("def foo() -> int raises RuntimeError, TypeError: ...")

  def test_external_function(self):
    self.check("def foo PYTHONCODE")


class ClassTest(_ParserTestBase):

  def test_no_parents(self):
    canonical = """\
      class Foo:
          pass
      """

    self.check(canonical, canonical)
    self.check("""\
      class Foo():
          pass
      """, canonical)

  def test_parents(self):
    self.check("""\
      class Foo(Bar):
          pass
    """)
    self.check("""\
      class Foo(Bar, Baz):
          pass
      """)

  def test_parent_remove_nothingtype(self):
    self.check("""\
      class Foo(nothing):
          pass
      """, """\
      class Foo:
          pass
      """)
    self.check("""\
      class Foo(Bar, nothing):
          pass
      """, """\
      class Foo(Bar):
          pass
      """)

  def test_metaclass(self):
    self.check("""\
      class Foo(metaclass=Meta):
          pass
      """)
    self.check("""\
      class Foo(Bar, metaclass=Meta):
          pass
      """)
    self.check_error("""\
      class Foo(badkeyword=Meta):
          pass
      """, 1, "Only 'metaclass' allowed as classdef kwarg")
    self.check_error("""\
      class Foo(metaclass=Meta, Bar):
          pass
      """, 1, "metaclass must be last argument")

  def test_shadow_pep484(self):
    self.check("""\
      class List:
          def bar(self) -> List: ...
      """)

  def test_no_body(self):
    canonical = """\
      class Foo:
          pass
      """
    # There are numerous ways to indicate an empty body.
    self.check(canonical, canonical)
    self.check("""\
      class Foo(): pass
      """, canonical)
    self.check("""\
      class Foo(): ...
      """, canonical)
    self.check("""\
      class Foo():
          ...
      """, canonical)
    self.check("""\
      class Foo():
          ...
      """, canonical)
    # pylint: disable=g-inconsistent-quotes
    self.check('''\
      class Foo():
          """docstring"""
          ...
      ''', canonical)
    self.check('''\
      class Foo():
          """docstring"""
      ''', canonical)

  def test_attribute(self):
    self.check("""\
      class Foo:
          a = ...  # type: int
      """)

  def test_method(self):
    self.check("""\
      class Foo:
          def a(self, x: int) -> str: ...
      """)

  def test_property(self):
    self.check("""\
      class Foo:
          @property
          def a(self) -> int
      """, """\
      class Foo:
          a = ...  # type: int
      """)

  def test_duplicate_name(self):
    self.check_error("""\
      class Foo:
          bar = ...  # type: int
          bar = ...  # type: str
      """, 1, "Duplicate identifier(s): bar")
    self.check_error("""\
      class Foo:
          def bar(self) -> int: ...
          bar = ...  # type: str
      """, 1, "Duplicate identifier(s): bar")
    # Multiple method defs are ok (needed for variant signatures).
    self.check("""\
      class Foo:
          def x(self) -> int: ...
          def x(self) -> str: ...
      """)


class IfTest(_ParserTestBase):

  def test_if_true(self):
    self.check("""\
      if sys.version_info == (2, 7, 6):
        x = ...  # type: int
      """, """\
      x = ...  # type: int""")

  def test_if_false(self):
    self.check("""\
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      """, "")

  def test_else_used(self):
    self.check("""\
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      else:
        y = ...  # type: str
      """, """\
      y = ...  # type: str""")

  def test_else_ignored(self):
    self.check("""\
      if sys.version_info == (2, 7, 6):
        x = ...  # type: int
      else:
        y = ...  # type: str
      """, """\
      x = ...  # type: int""")

  def test_elif_used(self):
    self.check("""\
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info == (2, 7, 6):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """\
      y = ...  # type: float""")

  def test_elif_preempted(self):
    self.check("""\
      if sys.version_info > (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info == (2, 7, 6):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """\
      x = ...  # type: int""")

  def test_elif_ignored(self):
    self.check("""\
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info == (4, 5, 6):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """\
      z = ...  # type: str""")

  def test_nested_if(self):
    self.check("""\
      if sys.version_info >= (2, 0):
        if sys.platform == "linux":
          a = ...  # type: int
        else:
          b = ...  # type: int
      else:
        if sys.platform == "linux":
          c = ...  # type: int
        else:
          d = ...  # type: int
      """, "a = ...  # type: int")

  # The remaining tests verify that actions with side effects only take affect
  # within a true block.

  def test_conditional_import(self):
    self.check("""\
      if sys.version_info == (2, 7, 6):
        from foo import Processed
      else:
        from foo import Ignored
      """, "from foo import Processed")

  def test_conditional_alias_or_constant(self):
    self.check("""\
      if sys.version_info == (2, 7, 6):
        x = Processed
      else:
        y = Ignored
      """, "x = Processed")

  def test_conditional_class(self):
    self.check("""\
      if sys.version_info == (2, 7, 6):
        class Processed: pass
      else:
        class Ignored: pass
      """, """\
      class Processed:
          pass
      """)

  def test_conditional_class_registration(self):
    # There is a bug in legacy, so this cannot be checked against the legacy
    # parser.
    #
    # Class registration allows a local class name to shadow a PEP 484 name.
    # The only time this is noticeable is when the PEP 484 name is one of the
    # capitalized names that gets converted to lower case (i.e. List -> list).
    # In these cases a non-shadowed name would be converted to lower case, and
    # a properly shadowed name would remain capitalized.  In the test below,
    # Dict should be registered, List should not be registered.  Thus after
    # the "if" statement Dict refers to the local Dict class and List refers
    # to the PEP 484 list class.
    self.check("""\
      if sys.version_info == (2, 7, 6):
        class Dict: pass
      else:
        class List: pass

      x = ...  # type: Dict
      y = ...  # type: List
      """, """\
      x = ...  # type: Dict
      y = ...  # type: list

      class Dict:
          pass
      """, legacy=False)

  def test_conditional_typevar(self):
    # The legacy parser does not handle this correctly - typevars are added
    # regardless of any conditions.
    self.check("""\
      if sys.version_info == (2, 7, 6):
        T = TypeVar('T')
      else:
        F = TypeVar('F')
      """, """\
        from typing import TypeVar

        T = TypeVar('T')""", legacy=False)


class ClassIfTest(_ParserTestBase):

  # These tests assume that IfTest has already covered the inner workings of
  # peer's functions.  Instead, they focus on verifying that if statements
  # under a class allow things that normally appear in a class (constants,
  # functions), and disallow statements that aren't allowed in a class (import,
  # etc).

  def test_conditional_constant(self):
    self.check("""\
      class Foo:
        if sys.version_info == (2, 7, 0):
          x = ...  # type: int
        elif sys.version_info == (2, 7, 6):
          y = ...  # type: str
        else:
          z = ...  # type: float
      """, """\
      class Foo:
          y = ...  # type: str
      """)

  def test_conditional_method(self):
    self.check("""\
      class Foo:
        if sys.version_info == (2, 7, 0):
          def a(self, x: int) -> str: ...
        elif sys.version_info == (2, 7, 6):
          def b(self, x: int) -> str: ...
        else:
          def c(self, x: int) -> str: ...
      """, """\
      class Foo:
          def b(self, x: int) -> str: ...
      """)

  def test_nested(self):
    self.check("""\
      class Foo:
        if sys.version_info > (2, 7, 0):
          if sys.version_info == (2, 7, 6):
            def b(self, x: int) -> str: ...
      """, """\
      class Foo:
          def b(self, x: int) -> str: ...
      """)

  def test_no_import(self):
    self.check_error("""\
      class Foo:
        if sys.version_info > (2, 7, 0):
          import foo
    """, 3, "syntax error")

  def test_no_alias(self):
    self.check_error("""\
      class Foo:
        if sys.version_info > (2, 7, 0):
          a = b
    """, 3, "syntax error")

  def test_no_class(self):
    self.check_error("""\
      class Foo:
        if sys.version_info > (2, 7, 0):
          class Bar: ...
    """, 3, "syntax error")

  def test_no_typevar(self):
    self.check_error("""\
      class Foo:
        if sys.version_info > (2, 7, 0):
          T = TypeVar('T')
    """, 3, "syntax error")


class ConditionTest(_ParserTestBase):

  def check_cond(self, condition, expected):
    out = "x = ...  # type: int" if expected else ""
    self.check("""\
      if %s:
        x = ...  # type: int
      """ % condition, out)

  def check_cond_error(self, condition, message):
    self.check_error("""\
      if %s:
        x = ...  # type: int
      """ % condition, 1, message)

  def test_version_eq(self):
    self.check_cond("sys.version_info == (2, 7, 5)", False)
    self.check_cond("sys.version_info == (2, 7, 6)", True)
    self.check_cond("sys.version_info == (2, 7, 7)", False)

  def test_version_ne(self):
    self.check_cond("sys.version_info != (2, 7, 5)", True)
    self.check_cond("sys.version_info != (2, 7, 6)", False)
    self.check_cond("sys.version_info != (2, 7, 7)", True)

  def test_version_lt(self):
    self.check_cond("sys.version_info < (2, 7, 5)", False)
    self.check_cond("sys.version_info < (2, 7, 6)", False)
    self.check_cond("sys.version_info < (2, 7, 7)", True)
    self.check_cond("sys.version_info < (2, 8, 0)", True)

  def test_version_le(self):
    self.check_cond("sys.version_info <= (2, 7, 5)", False)
    self.check_cond("sys.version_info <= (2, 7, 6)", True)
    self.check_cond("sys.version_info <= (2, 7, 7)", True)
    self.check_cond("sys.version_info <= (2, 8, 0)", True)

  def test_version_gt(self):
    self.check_cond("sys.version_info > (2, 6, 0)", True)
    self.check_cond("sys.version_info > (2, 7, 5)", True)
    self.check_cond("sys.version_info > (2, 7, 6)", False)
    self.check_cond("sys.version_info > (2, 7, 7)", False)

  def test_version_ge(self):
    self.check_cond("sys.version_info >= (2, 6, 0)", True)
    self.check_cond("sys.version_info >= (2, 7, 5)", True)
    self.check_cond("sys.version_info >= (2, 7, 6)", True)
    self.check_cond("sys.version_info >= (2, 7, 7)", False)

  def test_version_shorter_tuples(self):
    self.check_cond("sys.version_info >= (2,)", True)
    self.check_cond("sys.version_info >= (3,)", False)
    self.check_cond("sys.version_info >= (2, 7)", True)
    self.check_cond("sys.version_info >= (2, 8)", False)

  def test_version_error(self):
    self.check_cond_error('sys.version_info == "foo"',
                          "sys.version_info must be compared to a tuple")
    self.check_cond_error("sys.version_info == (1.2, 3)",
                          "only integers are allowed in version tuples")

  def test_platform_eq(self):
    self.check_cond('sys.platform == "linux"', True)
    self.check_cond('sys.platform == "win32"', False)

  def test_platform_error(self):
    self.check_cond_error("sys.platform == (1, 2, 3)",
                          "sys.platform must be compared to a string")
    self.check_cond_error('sys.platform < "linux"',
                          "sys.platform must be compared using == or !=")
    self.check_cond_error('sys.platform <= "linux"',
                          "sys.platform must be compared using == or !=")
    self.check_cond_error('sys.platform > "linux"',
                          "sys.platform must be compared using == or !=")
    self.check_cond_error('sys.platform >= "linux"',
                          "sys.platform must be compared using == or !=")

  def test_unsupported_condition(self):
    self.check_cond_error("foo.bar == (1, 2, 3)",
                          "Unsupported condition: 'foo.bar'")


class EntireFileTest(_ParserTestBase):

  def test_builtins(self):
    self.check(get_builtins_source(), expected=IGNORE)


class MemoryLeakTest(unittest.TestCase):

  def check(self, src):
    def parse():
      try:
        parser.parse_string(src)
      except parser.ParseError:
        # It is essential to clear the error, otherwise the system exc_info
        # will hold references to lots of stuff hanging off the exception.
        sys.exc_clear()

    # Sometimes parsing has side effects that are long-lived (lazy
    # initialization of shared instances, etc).  In order to prevent these
    # from looking like leaks, parse the source twice, using the gc objects
    # after the first pass as a baseline for the second pass.
    parse()
    gc.collect()
    before = gc.get_objects()
    parse()
    gc.collect()
    after = gc.get_objects()

    # Determine the ids of any leaked objects.
    before_ids = {id(x) for x in before}
    after_map = {id(x): x for x in after}
    leaked_ids = set(after_map) - before_ids
    leaked_ids.discard(id(before))
    if not leaked_ids:
      return

    # Include details about the leaked objects in the failure message.
    lines = ["Detected %d leaked objects" % len(leaked_ids)]
    for i in leaked_ids:
      obj = after_map[i]
      detail = str(obj)
      if len(detail) > 50:
        detail = detail[:50] + "..."
      lines.append("  <%s>  %s" % (type(obj).__name__, detail))
    self.fail("\n".join(lines))

  def test_builtins(self):
    # This has a little of everything.
    self.check(get_builtins_source())

  def test_error_in_class(self):
    self.check("""\
      class Foo:
        def m(): pass
        an error""")

  def test_error_in_function(self):
    self.check("""\
      def m(): pass
      def n(x: int, y: str) -> ->
      """)

  def test_error_within_if(self):
    self.check("""\
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
        this is an error
      """)


if __name__ == "__main__":
  unittest.main()
