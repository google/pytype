import hashlib
import os
import re
import textwrap

from pytype import utils
from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.tests import test_base
import six

import unittest

IGNORE = object()


def get_builtins_source(python_version):
  filename = "builtins/%d/__builtin__.pytd" % python_version[0]
  pytd_dir = os.path.dirname(pytd.__file__)
  with open(os.path.join(pytd_dir, filename)) as f:
    return f.read()


class _ParserTestBase(test_base.UnitTest):

  def check(self, src, expected=None, prologue=None, name=None,
            version=None, platform=None):
    """Check the parsing of src.

    This checks that parsing the source and then printing the resulting
    AST results in the expected text.

    Args:
      src: A source string.
      expected: Optional expected result string.  If not provided, src is
        used instead.  The special value IGNORE can be used to skip
        checking the parsed results against expected text.
      prologue: An optional prologue to be prepended to the expected text
        before comparisson.  Useful for imports that are introduced during
        printing the AST.
      name: The name of the module.
      version: A python version tuple (None for default value).
      platform: A platform string (None for default value).

    Returns:
      The parsed pytd.TypeDeclUnit.
    """
    version = version or self.python_version
    src = textwrap.dedent(src).lstrip()
    ast = parser.parse_string(src, name=name, python_version=version,
                              platform=platform)
    actual = pytd_utils.Print(ast)
    if expected != IGNORE:
      if expected is None:
        expected = src
      else:
        expected = textwrap.dedent(expected).lstrip()
      if prologue:
        expected = "%s\n\n%s" % (textwrap.dedent(prologue), expected)
      # Allow blank lines at the end of `expected` for prettier tests.
      self.assertMultiLineEqual(expected.rstrip(), actual)
    return ast

  def check_error(self, src, expected_line, message):
    """Check that parsing the src raises the expected error."""
    with self.assertRaises(parser.ParseError) as e:
      parser.parse_string(textwrap.dedent(src).lstrip(),
                          python_version=self.python_version)
    six.assertRegex(self, utils.message(e.exception), re.escape(message))
    self.assertEqual(expected_line, e.exception.line)


class ParseErrorTest(unittest.TestCase):

  def check(self, expected, *args, **kwargs):
    e = parser.ParseError(*args, **kwargs)
    self.assertMultiLineEqual(textwrap.dedent(expected).lstrip("\n"), str(e))

  def test_plain_error(self):
    self.check("""
        ParseError: my message""", "my message")

  def test_full_error(self):
    self.check("""
          File: "foo.py", line 123
            this is a test
                 ^
        ParseError: my message""", "my message", line=123, filename="foo.py",
               text="this is a test", column=6)

  def test_indented_text(self):
    self.check("""
          File: "foo.py", line 123
            this is a test
                 ^
        ParseError: my message""", "my message", line=123, filename="foo.py",
               text="          this is a test", column=16)

  def test_line_without_filename(self):
    self.check("""
          File: "None", line 1
        ParseError: my message""", "my message", line=1)

  def test_filename_without_line(self):
    self.check("""
          File: "foo.py", line None
        ParseError: my message""", "my message", filename="foo.py")

  def test_text_without_column(self):
    self.check("""
        ParseError: my message""", "my message", text="this is  a test")

  def test_column_without_text(self):
    self.check("        ParseError: my message", "my message", column=5)


class ParserTest(_ParserTestBase):

  def test_syntax_error(self):
    self.check_error("123", 1, "syntax error")

  def test_illegal_character(self):
    self.check_error("^", 1, "Illegal character '^'")

  def test_invalid_indentation(self):
    self.check_error("""
      class Foo:
        x = ... # type: int
       y""", 3, "Invalid indentation")

  def test_type_on_next_line(self):
    # TODO(dbaum): This probably should be an error.  Current behavior matches
    # legacy parser. Consider changing to an error.
    self.check("""
      a = ...
      # type: int""",
               """
      a: int""")

  def test_constant(self):
    self.check("x = ...", "x: Any", "from typing import Any")
    self.check("x: str")
    self.check("x = 0", "x: int")
    self.check("x = 0.0", "x: float")
    self.check_error("x = 123", 1,
                     "Only '0' allowed as int literal")
    self.check("x = 0.0", "x: float")
    self.check_error("x = 12.3", 1,
                     "Only '0.0' allowed as float literal")

  def test_string_constant(self):
    self.check("x = b''", "x: bytes")
    self.check("x = u''", "x: unicode")
    self.check('x = b""', "x: bytes")
    self.check('x = u""', "x: unicode")
    self.check("x = ''", "x: str")
    self.check('x = ""', "x: str")
    self.check_error("x = b'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")
    self.check_error("x = u'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")
    self.check_error("x = 'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")

  def test_constant_pep526(self):
    self.check("x : str", "x: str")
    self.check("x : str = ...", "x: str")

  def test_alias_or_constant(self):
    self.check("x = True", "x: bool")
    self.check("x = False", "x: bool")
    self.check("x = Foo")
    self.check("""
      class A:
          x = True""", """
      class A:
          x: bool
    """)
    self.check("""
      class A:
          x = ...  # type: int
          y = x
          z = y""", """
      class A:
          x: int
          y: int
          z: int
    """)

  def test_method_aliases(self):
    self.check("""
      class A:
          def x(self) -> int
          y = x
          z = y
          @classmethod
          def a(cls) -> str
          b = a
          c = b""", """
      class A:
          def x(self) -> int: ...
          @classmethod
          def a(cls) -> str: ...
          def y(self) -> int: ...
          def z(self) -> int: ...
          @classmethod
          def b(cls) -> str: ...
          @classmethod
          def c(cls) -> str: ...
    """)

  def test_slots(self):
    self.check("""
      class A:
          __slots__ = ...  # type: tuple
    """, """
      class A: ...
    """)
    self.check("""
      class A:
          __slots__ = ["foo", "bar", "baz"]
    """)
    self.check("""
      class A:
          __slots__ = []
    """)
    self.check_error("""
      __slots__ = ["foo", "bar"]
    """, 1, "__slots__ only allowed on the class level")
    self.check_error("""
      class A:
          __slots__ = ["foo", "bar"]
          __slots__ = ["foo", "bar", "baz"]
    """, 1, "Duplicate __slots__ declaration")
    self.check_error("""
      class A:
          __slots__ = ["foo", ?]
    """, 2, "syntax error")
    self.check_error("""
      class A:
          __slots__ = int
    """, 2, "__slots__ must be a list of strings")

  def test_nested_class(self):
    self.check("""
      class A:
          class B: ...
    """)

  def test_nested_class_alias(self):
    self.check("""
      class A:
          class B: ...
          C = A.B
    """, """
      from typing import Type

      class A:
          class B: ...
          C: Type[A.B]
    """)

  def test_nested_class_module_alias(self):
    self.check("""
      class A:
          class B: ...
      C = A.B
    """, """
      from typing import Type

      C: Type[A.B]

      class A:
          class B: ...
    """)

  def test_conditional_nested_class(self):
    self.check("""
      if sys.version_info < (3, 5):
        class A:
          class B: ...
    """, "")

  def test_import(self):
    self.check("import foo.bar.baz", "")
    self.check("import a as b")
    self.check("from foo.bar import baz")
    self.check("from foo.bar import baz as abc")
    self.check("from typing import NamedTuple, TypeVar", "")
    self.check("from foo.bar import *")
    self.check_error("from foo import * as bar", 1, "syntax error")
    self.check("from foo import a, b",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b)",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b, )",
               "from foo import a\nfrom foo import b")

  def test_from_import(self):
    ast = self.check("from foo import c\nclass Bar(c.X): ...", IGNORE)
    parent, = ast.Lookup("Bar").parents
    self.assertEqual(parent, pytd.NamedType("foo.c.X"))

  def test_duplicate_names(self):
    self.check_error("""
      def foo() -> int: ...
      foo = ... # type: int""",
                     None,
                     "Duplicate top-level identifier(s): foo")
    self.check_error("""
      from x import foo
      def foo() -> int: ...""",
                     None,
                     "Duplicate top-level identifier(s): foo")
    self.check_error("""
      X = ... # type: int
      class X: ...""",
                     None,
                     "Duplicate top-level identifier(s): X")
    self.check_error("""
      X = ... # type: int
      X = TypeVar('X')""",
                     None,
                     "Duplicate top-level identifier(s): X")
    # A function is allowed to appear multiple times.
    self.check("""
      def foo(x: int) -> int: ...
      def foo(x: str) -> str: ...""",
               """
      @overload
      def foo(x: int) -> int: ...
      @overload
      def foo(x: str) -> str: ...""")
    # @overload decorators should be properly round-tripped.
    self.check("""
      @overload
      def foo(x: int) -> int: ...
      @overload
      def foo(x: str) -> str: ...""")

  def test_type(self):
    self.check("x: str")
    self.check("x = ...  # type: (str)", "x: str")
    self.check("x: foo.bar.Baz", prologue="import foo.bar")
    self.check("x = ...  # type: ?", "x: Any",
               prologue="from typing import Any")
    self.check("x: nothing")
    self.check("x = ...  # type: int or str or float", """
                from typing import Union

                x: Union[int, str, float]""")
    self.check("x = ...  # type: int and str and float", """
                x: int and str and float""")

  def test_empty_union_or_intersection_or_optional(self):
    self.check_error("def f(x: typing.Union): ...", 1,
                     "Missing options to typing.Union")
    self.check_error("def f(x: typing.Intersection): ...", 1,
                     "Missing options to typing.Intersection")
    self.check_error("def f(x: typing.Optional): ...", 1,
                     "Missing options to typing.Optional")

  def test_optional_extra_parameters(self):
    self.check_error("def f(x: typing.Optional[int, str]): ...", 1,
                     "Too many options to typing.Optional")

  def test_alias_lookup(self):
    self.check("""
      from somewhere import Foo
      x = ...  # type: Foo
      """, """
      import somewhere

      from somewhere import Foo

      x: somewhere.Foo""")

  def test_type_params(self):
    ast = self.check("""
      from typing import TypeVar

      T = TypeVar('T')

      def func(x: T) -> T: ...""")
    # During parsing references to type paraemters are instances of NamedType.
    # They should be replaced by TypeParameter objects during post-processing.
    sig = ast.functions[0].signatures[0]
    self.assertIsInstance(sig.params[0].type, pytd.TypeParameter)
    self.assertIsInstance(sig.return_type, pytd.TypeParameter)

    # Check various illegal TypeVar arguments.
    self.check_error("T = TypeVar()", 1, "syntax error")
    self.check_error("T = TypeVar(*args)", 1, "syntax error")
    self.check_error("T = TypeVar(...)", 1, "syntax error")
    self.check_error("T = TypeVar('Q')", 1,
                     "TypeVar name needs to be 'Q' (not 'T')")
    self.check_error("T = TypeVar('T', covariant=True, int, float)", 1,
                     "syntax error")
    self.check_error("T = TypeVar('T', rumpelstiltskin=True)", 1,
                     "Unrecognized keyword")

  def test_type_param_arguments(self):
    self.check("""
      from typing import List, TypeVar

      T = TypeVar('T', List[int], List[str])""")
    self.check("""
      from typing import List, TypeVar

      T = TypeVar('T', bound=List[str])""")
    # 'covariant' and 'contravariant' are ignored for now.
    self.check("""
      from typing import TypeVar

      T = TypeVar('T', str, unicode, covariant=True)""", """
      from typing import TypeVar

      T = TypeVar('T', str, unicode)""")
    self.check("""
      import other_mod
      from typing import TypeVar

      T = TypeVar('T', other_mod.A, other_mod.B)""")

  def test_error_formatting(self):
    src = """
      class Foo:
        this is not valid"""
    with self.assertRaises(parser.ParseError) as e:
      parser.parse_string(textwrap.dedent(src).lstrip(), filename="foo.py",
                          python_version=self.python_version)
    self.assertMultiLineEqual(textwrap.dedent("""
        File: "foo.py", line 2
          this is not valid
               ^
      ParseError: syntax error, unexpected NAME, expecting ':' or '='
    """).strip("\n"), str(e.exception))

  def test_pep484_translations(self):
    ast = self.check("""
      x: None""")
    self.assertEqual(pytd.NamedType("NoneType"), ast.constants[0].type)

  def test_module_name(self):
    ast = self.check("x = ...  # type: int",
                     "foo.x: int",
                     name="foo")
    self.assertEqual("foo", ast.name)

  def test_no_module_name(self):
    # If the name is not specified, it is a digest of the source.
    src = ""
    ast = self.check(src)
    self.assertEqual(hashlib.md5(src.encode()).hexdigest(), ast.name)
    src = "x: int"
    ast = self.check(src)
    self.assertEqual(hashlib.md5(src.encode()).hexdigest(), ast.name)

  def test_pep84_aliasing(self):
    # This should not be done for the typing module itself.
    self.check("x = ... # type: Hashable",
               "typing.x: Hashable",
               name="typing")

  def test_module_class_clash(self):
    ast = parser.parse_string(textwrap.dedent("""
      from bar import X
      class bar:
        X = ... # type: ?
      y = bar.X.Baz
      z = X.Baz
    """), name="foo", python_version=self.python_version)
    self.assertEqual("foo.bar.X.Baz", ast.Lookup("foo.y").type.name)
    self.assertEqual("bar.X.Baz", ast.Lookup("foo.z").type.name)

  def test_trailing_list_comma(self):
    self.check("""
      from typing import Any, Callable

      x: Callable[
        [
          int,
          int,
        ],
        Any,
      ]
    """, """
      from typing import Any, Callable

      x: Callable[[int, int], Any]
    """)


class HomogeneousTypeTest(_ParserTestBase):

  def test_callable_parameters(self):
    self.check("""
      from typing import Callable

      x: Callable[[int, str], bool]""")
    self.check("""
      from typing import Callable

      x = ...  # type: Callable[..., bool]""", """
      from typing import Any, Callable

      x: Callable[Any, bool]""")
    self.check("""
      from typing import Any, Callable

      x: Callable[Any, bool]""")
    self.check("""
      from typing import Any, Callable

      x: Callable[[Any], bool]""")
    self.check("""
      from typing import Callable

      x: Callable[[], bool]""")
    self.check("""
      from typing import Callable

      x = ...  # type: Callable[[nothing], bool]""", """
      from typing import Callable

      x: Callable[[], bool]""")
    self.check("""
      from typing import Callable

      x = ...  # type: Callable[[int]]""", """
      from typing import Any, Callable

      x: Callable[[int], Any]""")
    self.check("""
      from typing import Callable

      x = ...  # type: Callable[[], ...]""", """
      from typing import Any, Callable

      x: Callable[[], Any]""")
    self.check_error(
        "import typing\n\nx = ...  # type: typing.Callable[int]", 3,
        "First argument to Callable must be a list of argument types")
    self.check_error(
        "import typing\n\nx = ...  # type: typing.Callable[[], bool, bool]", 3,
        "Expected 2 parameters to Callable, got 3")

  def test_ellipsis(self):
    # B[T, ...] becomes B[T].
    self.check("from typing import List\n\nx = ...  # type: List[int, ...]",
               "from typing import List\n\nx: List[int]")
    # Double ellipsis is not allowed.
    self.check_error("x = ...  # type: List[..., ...]", 1,
                     "not supported")
    # Tuple[T] and Tuple[T, ...] are distinct.
    self.check("from typing import Tuple\n\nx = ...  # type: Tuple[int]",
               "from typing import Tuple\n\nx: Tuple[int]")
    self.check("from typing import Tuple\n\nx = ...  # type: Tuple[int, ...]",
               "from typing import Tuple\n\nx: Tuple[int, ...]")

  def test_tuple(self):
    self.check("""
      from typing import Tuple

      x = ...  # type: Tuple[int, str]""",
               """
      from typing import Tuple

      x: Tuple[int, str]""")
    self.check("""
      from typing import Tuple

      x = ...  # type: Tuple[int, str, ...]""",
               """
      from typing import Any, Tuple

      x: Tuple[int, str, Any]""")

  def test_empty_tuple(self):
    self.check("""
      from typing import Tuple

      def f() -> Tuple[()]: ...
    """, """
      from typing import Tuple

      def f() -> Tuple[()]: ...
    """)

  def test_simple(self):
    self.check("x: Foo[int, str]")

  def test_type_tuple(self):
    self.check("x = (str, bytes)",
               "x: tuple")
    self.check("x = (str, bytes,)",
               "x: tuple")
    self.check("x = (str,)",
               "x: tuple")
    self.check("x = str,",
               "x: tuple")


class NamedTupleTest(_ParserTestBase):

  def test_no_fields(self):
    self.check("x = ...  # type: NamedTuple('foo', [])", """
      from typing import Any, Tuple, Type, TypeVar

      x: `namedtuple-foo-0`

      _Tnamedtuple-foo-0 = TypeVar('_Tnamedtuple-foo-0', bound=`namedtuple-foo-0`)

      class `namedtuple-foo-0`(Tuple[()]):
          __slots__ = []
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-foo-0`]) -> `_Tnamedtuple-foo-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
      """)

  def test_multiple_fields(self):
    expected = """
      from typing import Any, Tuple, Type, TypeVar

      x: `namedtuple-foo-0`

      _Tnamedtuple-foo-0 = TypeVar('_Tnamedtuple-foo-0', bound=`namedtuple-foo-0`)

      class `namedtuple-foo-0`(Tuple[int, str]):
          __slots__ = ["a", "b"]
          a: int
          b: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-foo-0`], a: int, b: str) -> `_Tnamedtuple-foo-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
    """
    self.check("x = ...  # type: NamedTuple('foo', [('a', int), ('b', str)])",
               expected)
    self.check("x = ...  # type: NamedTuple('foo', [('a', int), ('b', str),])",
               expected)
    self.check("x = ...  # type: NamedTuple('foo', [('a', int,), ('b', str),])",
               expected)

  # pylint: disable=line-too-long
  def test_dedup_basename(self):
    self.check("""
      x = ...  # type: NamedTuple('foo', [('a', int,)])
      y = ...  # type: NamedTuple('foo', [('b', str,)])""",
               """
      from typing import Any, Tuple, Type, TypeVar

      x: `namedtuple-foo-0`
      y: `namedtuple-foo-1`

      _Tnamedtuple-foo-0 = TypeVar('_Tnamedtuple-foo-0', bound=`namedtuple-foo-0`)
      _Tnamedtuple-foo-1 = TypeVar('_Tnamedtuple-foo-1', bound=`namedtuple-foo-1`)

      class `namedtuple-foo-0`(Tuple[int]):
          __slots__ = ["a"]
          a: int
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-foo-0`], a: int) -> `_Tnamedtuple-foo-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...

      class `namedtuple-foo-1`(Tuple[str]):
          __slots__ = ["b"]
          b: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-foo-1`], b: str) -> `_Tnamedtuple-foo-1`: ...
          def __init__(self, *args, **kwargs) -> None: ...
        """)
  # pylint: enable=line-too-long

  def test_assign_namedtuple(self):
    self.check("X = NamedTuple('X', [])", """
      from typing import Any, Tuple, Type, TypeVar

      X = `namedtuple-X-0`

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[()]):
          __slots__ = []
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`]) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
    """)

  def test_subclass_namedtuple(self):
    self.check("class X(NamedTuple('X', [])): ...", """
      from typing import Any, Tuple, Type, TypeVar

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[()]):
          __slots__ = []
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`]) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...

      class X(`namedtuple-X-0`): ...
    """)

  def test_trailing_comma(self):
    self.check("""
      from typing import NamedTuple
      Foo = NamedTuple(
          "Foo",
          [
              ("a", int),
              ("b", str),
          ],
      )
    """, """
      from typing import Any, Tuple, Type, TypeVar

      Foo = `namedtuple-Foo-0`

      _Tnamedtuple-Foo-0 = TypeVar('_Tnamedtuple-Foo-0', bound=`namedtuple-Foo-0`)

      class `namedtuple-Foo-0`(Tuple[int, str]):
          __slots__ = ["a", "b"]
          a: int
          b: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-Foo-0`], a: int, b: str) -> `_Tnamedtuple-Foo-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
    """)

  def test_collections_trailing_comma(self):
    self.check("""
      from collections import namedtuple
      Foo = namedtuple(
        "Foo",
        [
          "a",
          "b",
        ],
      )
    """, """
      from typing import Any, Tuple, Type, TypeVar

      from collections import namedtuple
      Foo = `namedtuple-Foo-0`

      _Tnamedtuple-Foo-0 = TypeVar('_Tnamedtuple-Foo-0', bound=`namedtuple-Foo-0`)

      class `namedtuple-Foo-0`(Tuple[Any, Any]):
          __slots__ = ["a", "b"]
          a: Any
          b: Any
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-Foo-0`], a, b) -> `_Tnamedtuple-Foo-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
    """)

  def test_collections_namedtuple(self):
    expected = """
      from typing import Any, Tuple, Type, TypeVar

      from collections import namedtuple
      X = `namedtuple-X-0`

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[Any]):
          __slots__ = ["y"]
          y: Any
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`], y) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...
    """
    self.check("""
      from collections import namedtuple
      X = namedtuple("X", ["y"])
    """, expected)
    self.check("""
      from collections import namedtuple
      X = namedtuple("X", ["y",])
    """, expected)

  def test_typing_namedtuple_class(self):
    self.check("""
      from typing import NamedTuple
      class X(NamedTuple):
        y: int
        z: str
    """, """
      from typing import Any, Tuple, Type, TypeVar

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[int, str]):
          __slots__ = ["y", "z"]
          y: int
          z: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`], y: int, z: str) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...

      class X(`namedtuple-X-0`): ...
    """)

  def test_typing_namedtuple_class_with_method(self):
    self.check("""
      from typing import NamedTuple
      class X(NamedTuple):
        y: int
        z: str
        def foo(self) -> None: ...
    """, """
      from typing import Any, Tuple, Type, TypeVar

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[int, str]):
          __slots__ = ["y", "z"]
          y: int
          z: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`], y: int, z: str) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...

      class X(`namedtuple-X-0`):
          def foo(self) -> None: ...
    """)

  def test_typing_namedtuple_class_multi_inheritance(self):
    self.check("""
      from typing import NamedTuple
      class X(dict, NamedTuple):
        y: int
        z: str
    """, """
      from typing import Any, Tuple, Type, TypeVar

      _Tnamedtuple-X-0 = TypeVar('_Tnamedtuple-X-0', bound=`namedtuple-X-0`)

      class `namedtuple-X-0`(Tuple[int, str]):
          __slots__ = ["y", "z"]
          y: int
          z: str
          _asdict: Any
          __dict__: Any
          _fields: Any
          __getnewargs__: Any
          __getstate__: Any
          _make: Any
          _replace: Any
          def __new__(cls: Type[`_Tnamedtuple-X-0`], y: int, z: str) -> `_Tnamedtuple-X-0`: ...
          def __init__(self, *args, **kwargs) -> None: ...

      class X(dict, `namedtuple-X-0`): ...
    """)

  def test_multi_namedtuple_parent(self):
    self.check_error("""
      from typing import NamedTuple
      class X(NamedTuple, NamedTuple): ...
    """, 2, "cannot inherit from bare NamedTuple more than once")


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
               "def foo(x = ...) -> int: ...")
    self.check("def foo(x = xyz) -> int: ...",
               "def foo(x = ...) -> int: ...")
    self.check("def foo(x = ...) -> int: ...",
               "def foo(x = ...) -> int: ...")
    # Defaults are ignored if a declared type is present.
    self.check("def foo(x: str = 123) -> int: ...",
               "def foo(x: str = ...) -> int: ...")
    self.check("def foo(x: str = None) -> int: ...",
               "def foo(x: str = ...) -> int: ...")
    # Allow but do not preserve a trailing comma in the param list.
    self.check("def foo(x: int, y: str = ..., z: bool,) -> int: ...",
               "def foo(x: int, y: str = ..., z: bool) -> int: ...")

  def test_star_params(self):
    self.check("def foo(*, x) -> str: ...")
    self.check("def foo(x: int, *args) -> str: ...")
    self.check("def foo(x: int, *args, key: int = ...) -> str: ...")
    self.check("def foo(x: int, *args: float) -> str: ...")
    self.check("def foo(x: int, **kwargs) -> str: ...")
    self.check("def foo(x: int, **kwargs: float) -> str: ...")
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

  def test_typeignore(self):
    self.check("def foo() -> int:  # type: ignore\n  ...",
               "def foo() -> int: ...")
    self.check("def foo() -> int: ...  # type: ignore",
               "def foo() -> int: ...")
    self.check("def foo() -> int: pass  # type: ignore",
               "def foo() -> int: ...")
    self.check("def foo(x) -> int: # type: ignore\n  x=List[int]",
               "def foo(x) -> int:\n    x = List[int]")
    self.check("""
               def foo(x: int,  # type: ignore
                       y: str) -> bool: ...""",
               "def foo(x: int, y: str) -> bool: ...")
    self.check("""
      class Foo:
          bar: str  # type: ignore
    """, """
      class Foo:
          bar: str
    """)
    self.check("""
      class Foo:
          bar = ...  # type: str  # type: ignore
    """, """
      class Foo:
          bar: str
    """)
    self.check("""
      class Foo:
          bar: str = ...  # type: ignore
    """, """
      class Foo:
          bar: str
    """)

  def test_decorators(self):
    # These tests are a bit questionable because most of the decorators only
    # make sense for methods of classes.  But this at least gives us some
    # coverage of the decorator logic.  More sensible tests can be created once
    # classes are implemented.
    self.check("""
      @overload
      def foo() -> int: ...""",
               """
      def foo() -> int: ...""")

    # Accept and disregard type: ignore comments on a decorator
    self.check("""
      @overload
      def foo() -> int: ...
      @overload  # type: ignore  # unsupported signature
      def foo(bool) -> int: ...""",
               """
      @overload
      def foo() -> int: ...
      @overload
      def foo(bool) -> int: ...""")

    self.check("""
      @abstractmethod
      def foo() -> int: ...""",
               """
      @abstractmethod
      def foo() -> int: ...""")

    self.check("""
      @abc.abstractmethod
      def foo() -> int: ...""",
               """
      @abstractmethod
      def foo() -> int: ...""")

    self.check("""
      @staticmethod
      def foo() -> int: ...""")

    self.check("""
      @classmethod
      def foo() -> int: ...""")

    self.check("""
      @coroutine
      def foo() -> int: ...""")

    self.check("""
      @asyncio.coroutine
      def foo() -> int: ...""",
               """
      @coroutine
      def foo() -> int: ...""")

    self.check("""
      @asyncio.coroutine
      def foo() -> int: ...
      @coroutines.coroutine
      def foo() -> int: ...
      @coroutine
      def foo() -> str: ...""",
               """
      @coroutine
      @overload
      def foo() -> int: ...
      @coroutine
      @overload
      def foo() -> int: ...
      @coroutine
      @overload
      def foo() -> str: ...""")

    self.check_error("""
      def foo() -> str: ...
      @coroutine
      def foo() -> int: ...""",
                     None,
                     "Overloaded signatures for foo disagree on "
                     "coroutine decorators")

    self.check_error("""
      @property
      def foo(self) -> int""",
                     None,
                     "Module-level functions with property decorators: foo")

    self.check_error("""
      @foo.setter
      def foo(self, x) -> int: ...""",
                     None,
                     "Module-level functions with property decorators: foo")

    self.check_error("""
      @classmethod
      @staticmethod
      def foo() -> int: ...""",
                     3,
                     "Too many decorators for foo")

  def test_type_check_only(self):
    self.check("""
      from typing import type_check_only
      @type_check_only
      def f() -> None: ...
    """, "def f() -> None: ...")

  def test_type_check_only_class(self):
    self.check("""
      from typing import type_check_only
      @type_check_only
      class Foo: ...
    """, "class Foo: ...")

  def test_bad_decorated_class(self):
    self.check_error("""
      @classmethod
      class Foo: ...
    """, 2, "Unsupported class decorators: classmethod")

  def test_empty_body(self):
    self.check("def foo() -> int: ...")
    self.check("def foo() -> int",
               "def foo() -> int: ...")
    self.check("def foo() -> int: pass",
               "def foo() -> int: ...")
    self.check("""
      def foo() -> int:
        ...""",
               """
      def foo() -> int: ...""")
    self.check("""
      def foo() -> int:
        pass""",
               """
      def foo() -> int: ...""")
    self.check("""
      def foo() -> int:
        '''doc string'''""",
               """
      def foo() -> int: ...""")

  def test_mutators(self):
    # Mutators.
    self.check("""
      def foo(x) -> int:
          x = int""")
    self.check_error("""
      def foo(x) -> int:
          y = int""", 1, "No parameter named y")

  def test_exceptions(self):
    self.check("""
      def foo(x) -> int:
          raise Error""",
               """
      def foo(x) -> int:
          raise Error()""")
    self.check("""
      def foo(x) -> int:
          raise Error()""")
    self.check("""
      def foo() -> int:
          raise RuntimeError()
          raise TypeError()""")
    self.check("""
      def foo() -> int:
          raise Bar.Error()""", prologue="import Bar")

  def test_return(self):
    self.check("def foo() -> int: ...")
    self.check("def foo(): ...",
               "def foo() -> Any: ...",
               prologue="from typing import Any")

  def test_async(self):
    self.check("async def foo() -> int: ...",
               "def foo() -> Coroutine[Any, Any, int]: ...",
               prologue="from typing import Any, Coroutine")


class ClassTest(_ParserTestBase):

  def test_no_parents(self):
    canonical = """
      class Foo: ...
      """

    self.check(canonical, canonical)
    self.check("""
      class Foo():
          pass
      """, canonical)

  def test_parents(self):
    self.check("""
      class Foo(Bar): ...
    """)
    self.check("""
      class Foo(Bar, Baz): ...
      """)

  def test_parent_remove_nothingtype(self):
    self.check("""
      class Foo(nothing): ...
      """, """
      class Foo: ...
      """)
    self.check("""
      class Foo(Bar, nothing): ...
      """, """
      class Foo(Bar): ...
      """)

  def test_class_type_ignore(self):
    canonical = """
      class Foo:  # type: ignore
          pass
      class Bar(Foo):  # type: ignore
          pass
      """
    self.check(canonical, """
      class Foo: ...

      class Bar(Foo): ...
    """)

  def test_metaclass(self):
    self.check("""
      class Foo(metaclass=Meta): ...
      """)
    self.check("""
      class Foo(Bar, metaclass=Meta): ...
      """)
    self.check_error("""
      class Foo(badkeyword=Meta): ...
      """, 1, "Only 'metaclass' allowed as classdef kwarg")
    self.check_error("""
      class Foo(metaclass=Meta, Bar): ...
      """, 1, "metaclass must be last argument")

  def test_shadow_pep484(self):
    self.check("""
      class List:
          def bar(self) -> List: ...
      """)

  def test_no_body(self):
    canonical = """
      class Foo: ...
      """
    # There are numerous ways to indicate an empty body.
    self.check(canonical, canonical)
    self.check("""
      class Foo(): pass
      """, canonical)
    self.check("""
      class Foo():
          pass
      """, canonical)
    self.check("""
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
    # Accept type: ignore with empty body
    self.check("""
      class Foo: ...  # type: ignore
      """, canonical)
    self.check("""
      class Foo: # type: ignore
          pass
      """, canonical)

  def test_attribute(self):
    self.check("""
      class Foo:
          a: int
      """)

  def test_method(self):
    self.check("""
      class Foo:
          def a(self, x: int) -> str: ...
      """)

  def test_property(self):
    self.check("""
      class Foo:
          @property
          def a(self) -> int
      """, """
      class Foo:
          a: int
      """)

  def test_duplicate_name(self):
    self.check_error("""
      class Foo:
          bar = ...  # type: int
          bar = ...  # type: str
      """, 1, "Duplicate identifier(s): bar")
    self.check_error("""
      class Foo:
          def bar(self) -> int: ...
          bar = ...  # type: str
      """, 1, "Duplicate identifier(s): bar")
    # Multiple method defs are ok (needed for variant signatures).
    self.check("""
      class Foo:
          @overload
          def x(self) -> int: ...
          @overload
          def x(self) -> str: ...
      """)

  def test_protocol_parent(self):
    self.check("""
      from typing import Protocol

      class Foo(Protocol): ...
    """)

  def test_parameterized_protocol_parent(self):
    self.check("""
      from typing import Protocol, TypeVar

      T = TypeVar('T')

      class Foo(Protocol[T]): ...
    """, """
      from typing import Generic, Protocol, TypeVar

      T = TypeVar('T')

      class Foo(Protocol, Generic[T]): ...
    """)

  def test_bad_typevar_in_mutation(self):
    self.check_error("""
      from typing import Generic, TypeVar

      S = TypeVar('S')
      T = TypeVar('T')
      U = TypeVar('U')
      V = TypeVar('V')

      class Foo(Generic[T]):
        def __init__(self, x: S):
          self = Generic[S, T, U, V]
     """, None, "Type parameter(s) {U, V}")


class IfTest(_ParserTestBase):

  def test_if_true(self):
    self.check("""
      if sys.version_info >= (3, 5, 0):
        x = ...  # type: int
      """, """
      x: int""")

  def test_if_false(self):
    self.check("""
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      """, "")

  def test_else_used(self):
    self.check("""
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      else:
        y = ...  # type: str
      """, """
      y: str""")

  def test_else_ignored(self):
    self.check("""
      if sys.version_info >= (3, 5, 0):
        x = ...  # type: int
      else:
        y = ...  # type: str
      """, """
      x: int""")

  def test_elif_used(self):
    self.check("""
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info >= (3, 5, 0):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """
      y: float""")

  def test_elif_preempted(self):
    self.check("""
      if sys.version_info > (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info >= (3, 5, 0):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """
      x: int""")

  def test_elif_ignored(self):
    self.check("""
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
      elif sys.version_info == (4, 5, 6):
        y = ...  # type: float
      else:
        z = ...  # type: str
      """, """
      z: str""")

  def test_nested_if(self):
    self.check("""
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
      """, "a: int")

  def test_if_or(self):
    self.check("""
      if sys.version_info >= (2, 0) or sys.version_info < (0, 0, 0):
        a = ...  # type: int
      if sys.version_info < (0, 0, 0) or sys.version_info >= (2, 0):
        b = ...  # type: int
      if sys.version_info < (0, 0, 0) or sys.version_info > (4,):
        c = ...  # type: int
      if sys.version_info >= (2, 0) or sys.version_info >= (4, 7):
        d = ...  # type: int
      if (sys.platform == "windows" or sys.version_info < (0,) or
          sys.version_info >= (3, 5)):
        e = ...  # type: int
    """, """
      a: int
      b: int
      d: int
      e: int""")

  def test_if_and(self):
    self.check("""
      if sys.version_info >= (3, 0) and sys.version_info < (4, 0):
        a = ...  # type: int
      if sys.version_info >= (3, 0) and sys.version_info >= (4, 0):
        b = ...  # type: int
    """, """
      a: int""")

  # The remaining tests verify that actions with side effects only take effect
  # within a true block.

  def test_conditional_import(self):
    self.check("""
      if sys.version_info >= (3, 5, 0):
        from foo import Processed
      else:
        from foo import Ignored
      """, "from foo import Processed")

  def test_conditional_alias_or_constant(self):
    self.check("""
      if sys.version_info >= (3, 5, 0):
        x = Processed
      else:
        y = Ignored
      """, "x = Processed")

  def test_conditional_class(self):
    self.check("""
      if sys.version_info >= (3, 5, 0):
        class Processed: ...
      else:
        class Ignored: ...
      """, """
      class Processed: ...
      """)

  def test_conditional_class_registration(self):
    # Class registration allows a local class name to shadow a PEP 484 name.
    # The only time this is noticeable is when the PEP 484 name is one of the
    # capitalized names that gets converted to lower case (i.e. List -> list).
    # In these cases a non-shadowed name would be converted to lower case, and
    # a properly shadowed name would remain capitalized.  In the test below,
    # Dict should be registered, List should not be registered.  Thus after
    # the "if" statement Dict refers to the local Dict class and List refers
    # to the PEP 484 list class.
    self.check("""
      from typing import List
      if sys.version_info >= (3, 5, 0):
        class Dict: ...
      else:
        class List: ...

      x = ...  # type: Dict
      y = ...  # type: List
      """, """
      x: Dict
      y: list

      class Dict: ...
      """)

  def test_conditional_typevar(self):
    # The legacy parser did not handle this correctly - typevars are added
    # regardless of any conditions.
    self.check("""
      if sys.version_info >= (3, 5, 0):
        T = TypeVar('T')
      else:
        F = TypeVar('F')
      """, """
        from typing import TypeVar

        T = TypeVar('T')""")


class ClassIfTest(_ParserTestBase):

  # These tests assume that IfTest has already covered the inner workings of
  # peer's functions.  Instead, they focus on verifying that if statements
  # under a class allow things that normally appear in a class (constants,
  # functions), and disallow statements that aren't allowed in a class (import,
  # etc).

  def test_conditional_constant(self):
    self.check("""
      class Foo:
        if sys.version_info == (3, 4, 0):
          x = ...  # type: int
        elif sys.version_info >= (3, 5, 0):
          y = ...  # type: str
        else:
          z = ...  # type: float
      """, """
      class Foo:
          y: str
      """)

  def test_conditional_method(self):
    self.check("""
      class Foo:
        if sys.version_info == (3, 4, 0):
          def a(self, x: int) -> str: ...
        elif sys.version_info >= (3, 5, 0):
          def b(self, x: int) -> str: ...
        else:
          def c(self, x: int) -> str: ...
      """, """
      class Foo:
          def b(self, x: int) -> str: ...
      """)

  def test_nested(self):
    self.check("""
      class Foo:
        if sys.version_info > (3, 4, 0):
          if sys.version_info >= (3, 5, 0):
            def b(self, x: int) -> str: ...
      """, """
      class Foo:
          def b(self, x: int) -> str: ...
      """)

  def test_no_import(self):
    self.check_error("""
      class Foo:
        if sys.version_info > (3, 4, 0):
          import foo
    """, 3, "syntax error")

  def test_bad_alias(self):
    self.check_error("""
      class Foo:
        if sys.version_info > (3, 4, 0):
          a = b
    """, 1, "Illegal value for alias 'a'")

  def test_no_class(self):
    self.check("""
      class Foo:
        if sys.version_info <= (3, 4, 0):
          class Bar: ...
    """, """
      class Foo: ...
    """)

  def test_no_typevar(self):
    self.check_error("""
      class Foo:
        if sys.version_info > (3, 4, 0):
          T = TypeVar('T')
    """, 3, "syntax error")


class ConditionTest(_ParserTestBase):

  def check_cond(self, condition, expected, **kwargs):
    out = "x: int" if expected else ""
    if "version" not in kwargs:
      kwargs["version"] = (3, 6, 5)
    self.check("""
      if %s:
        x = ...  # type: int
      """ % condition, out, **kwargs)

  def check_cond_error(self, condition, message):
    self.check_error("""
      if %s:
        x = ...  # type: int
      """ % condition, 1, message)

  def test_version_eq(self):
    self.check_cond("sys.version_info == (3, 6, 4)", False)
    self.check_cond("sys.version_info == (3, 6, 5)", True)
    self.check_cond("sys.version_info == (3, 6, 6)", False)

  def test_version_ne(self):
    self.check_cond("sys.version_info != (3, 6, 4)", True)
    self.check_cond("sys.version_info != (3, 6, 5)", False)
    self.check_cond("sys.version_info != (3, 6, 6)", True)

  def test_version_lt(self):
    self.check_cond("sys.version_info < (3, 6, 4)", False)
    self.check_cond("sys.version_info < (3, 6, 5)", False)
    self.check_cond("sys.version_info < (3, 6, 6)", True)
    self.check_cond("sys.version_info < (3, 7, 0)", True)

  def test_version_le(self):
    self.check_cond("sys.version_info <= (3, 6, 4)", False)
    self.check_cond("sys.version_info <= (3, 6, 5)", True)
    self.check_cond("sys.version_info <= (3, 6, 6)", True)
    self.check_cond("sys.version_info <= (3, 7, 0)", True)

  def test_version_gt(self):
    self.check_cond("sys.version_info > (3, 6, 0)", True)
    self.check_cond("sys.version_info > (3, 6, 4)", True)
    self.check_cond("sys.version_info > (3, 6, 5)", False)
    self.check_cond("sys.version_info > (3, 6, 6)", False)

  def test_version_ge(self):
    self.check_cond("sys.version_info >= (3, 6, 0)", True)
    self.check_cond("sys.version_info >= (3, 6, 4)", True)
    self.check_cond("sys.version_info >= (3, 6, 5)", True)
    self.check_cond("sys.version_info >= (3, 6, 6)", False)

  def test_version_item(self):
    self.check_cond("sys.version_info[0] == 3", True)

  def test_version_slice(self):
    self.check_cond("sys.version_info[:] == (3, 6, 5)", True)
    self.check_cond("sys.version_info[:2] == (3, 6)", True)
    self.check_cond("sys.version_info[2:] == (5,)", True)
    self.check_cond("sys.version_info[0:1] == (3,)", True)
    self.check_cond("sys.version_info[::] == (3, 6, 5)", True)
    self.check_cond("sys.version_info[1::] == (6, 5)", True)
    self.check_cond("sys.version_info[:2:] == (3, 6)", True)
    self.check_cond("sys.version_info[::-2] == (5, 3)", True)
    self.check_cond("sys.version_info[1:3:] == (6, 5)", True)
    self.check_cond("sys.version_info[1::2] == (6,)", True)
    self.check_cond("sys.version_info[:2:2] == (3,)", True)
    self.check_cond("sys.version_info[3:1:-1] == (5,)", True)

  def test_version_shorter_tuples(self):
    self.check_cond("sys.version_info == (3,)", True, version=(3, 0, 0))
    self.check_cond("sys.version_info == (3, 0)", True, version=(3, 0, 0))
    self.check_cond("sys.version_info == (3, 0, 0)", True, version=(3, 0, 0))
    self.check_cond("sys.version_info == (3,)", False, version=(3, 0, 1))
    self.check_cond("sys.version_info == (3, 0)", False, version=(3, 0, 1))
    self.check_cond("sys.version_info > (3,)", True, version=(3, 0, 1))
    self.check_cond("sys.version_info > (3, 0)", True, version=(3, 0, 1))
    self.check_cond("sys.version_info == (3, 0, 0)", True, version=(3,))
    self.check_cond("sys.version_info == (3, 0, 0)", True, version=(3, 0))

  def test_version_slice_shorter_tuples(self):
    self.check_cond("sys.version_info[:2] == (3,)", True, version=(3, 0, 1))
    self.check_cond("sys.version_info[:2] == (3, 0)", True, version=(3, 0, 1))
    self.check_cond(
        "sys.version_info[:2] == (3, 0, 0)", True, version=(3, 0, 1))
    self.check_cond("sys.version_info[:2] == (3,)", False, version=(3, 1, 0))
    self.check_cond("sys.version_info[:2] == (3, 0)", False, version=(3, 1, 0))
    self.check_cond("sys.version_info[:2] > (3,)", True, version=(3, 1, 0))
    self.check_cond("sys.version_info[:2] > (3, 0)", True, version=(3, 1, 0))
    self.check_cond(
        "sys.version_info[:2] == (3, 0, 0)", True, version=(3,))
    self.check_cond(
        "sys.version_info[:2] == (3, 0, 0)", True, version=(3, 0))

  def test_version_error(self):
    self.check_cond_error('sys.version_info == "foo"',
                          "sys.version_info must be compared to a tuple of "
                          "integers")
    self.check_cond_error("sys.version_info == (1.2, 3)",
                          "sys.version_info must be compared to a tuple of "
                          "integers")
    self.check_cond_error("sys.version_info[0] == 2.0",
                          "an element of sys.version_info must be compared to "
                          "an integer")
    self.check_cond_error("sys.version_info[0] == (2,)",
                          "an element of sys.version_info must be compared to "
                          "an integer")
    self.check_cond_error("sys.version_info[:2] == (2.0, 7)",
                          "sys.version_info must be compared to a tuple of "
                          "integers")
    self.check_cond_error("sys.version_info[:2] == 2",
                          "sys.version_info must be compared to a tuple of "
                          "integers")
    self.check_cond_error("sys.version_info[42] == 42",
                          "tuple index out of range")

  def test_platform_eq(self):
    self.check_cond('sys.platform == "linux"', True)
    self.check_cond('sys.platform == "win32"', False)
    self.check_cond('sys.platform == "foo"', True, platform="foo")

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


class PropertyDecoratorTest(_ParserTestBase):
  """Tests that cover _parse_signature_as_property()."""

  def test_property_with_type(self):
    expected = """
      class A:
          name: str
    """

    # The return type of @property is used for the property type.
    self.check("""
      class A:
          @property
          def name(self) -> str:...
      """, expected)

    self.check("""
      class A:
          @name.setter
          def name(self, value: str) -> None: ...
      """, """
      from typing import Any

      class A:
          name: Any
      """)

    self.check("""
      class A:
          @property
          def name(self) -> str:...

          @name.setter
          def name(self, value: str) -> None: ...
      """, expected)

    self.check("""
      class A:
          @property
          def name(self) -> str:...

          @name.setter
          def name(self, value) -> None: ...
      """, expected)

    self.check("""
      class A:
          @property
          def name(self) -> str:...

          @name.setter
          def name(self, value: int) -> None: ...
      """, expected)

  def test_property_decorator_any_type(self):
    expected = """
          from typing import Any

          class A:
              name: Any
              """

    self.check("""
      class A:
          @property
          def name(self): ...
      """, expected)

    self.check("""
      class A:
          @name.setter
          def name(self, value): ...
      """, expected)

    self.check("""
      class A:
          @name.deleter
          def name(self): ...
      """, expected)

    self.check("""
      class A:
          @name.setter
          def name(self, value): ...

          @name.deleter
          def name(self): ...
      """, expected)

  def test_property_decorator_bad_syntax(self):
    self.check_error("""
      class A(object):
          @property
          def name(self, bad_arg): ...
    """, 1, "Unhandled decorator: property")

    self.check_error("""
      class A(object):
          @name.setter
          def name(self): ...
      """, 1, "Unhandled decorator: name.setter")

    self.check_error("""
      class A(object):
          @name.foo
          def name(self): ...
      """, 1, "Unhandled decorator: name.foo")

    self.check_error("""
      class A(object):
          @notname.deleter
          def name(self): ...
      """, 1, "Unhandled decorator: notname.deleter")

    self.check_error("""
      class A(object):
          @property
          @staticmethod
          def name(self): ...
      """, 4, "Too many decorators for name")

    self.check_error("""
      @property
      def name(self): ...
      """, None, "Module-level functions with property decorators: name")

  def test_property_getter(self):
    self.check("""
      class A:
        @property
        def name(self) -> str: ...

        @name.getter
        def name(self) -> int: ...
    """, """
    from typing import Union

    class A:
        name: Union[str, int]
    """)


class MergeSignaturesTest(_ParserTestBase):

  def test_property(self):
    self.check("""
      class A:
          @property
          def name(self) -> str: ...
      """, """
      class A:
          name: str
      """)

  def test_merge_property_types(self):
    self.check("""
      class A:
          @property
          def name(self) -> str: ...

          @property
          def name(self) -> int: ...
      """, """
      from typing import Union

      class A:
          name: Union[str, int]
      """)

    self.check("""
      class A:
          @property
          def name(self) -> str: ...

          @property
          def name(self): ...
    """, """
      from typing import Any

      class A:
          name: Any
    """)

  def test_method(self):
    self.check("""
      class A:
          def name(self) -> str: ...
      """)

  def test_merged_method(self):
    ast = self.check("""
      def foo(x: int) -> str: ...
      def foo(x: str) -> str: ...""",
                     """
      @overload
      def foo(x: int) -> str: ...
      @overload
      def foo(x: str) -> str: ...""")
    self.assertEqual(len(ast.functions), 1)
    foo = ast.functions[0]
    self.assertEqual(len(foo.signatures), 2)

  def test_method_and_property_error(self):
    self.check_error("""
      class A(object):
          @property
          def name(self): ...

          def name(self): ...
      """, 1, "Overloaded signatures for name disagree on decorators")

  def test_overloaded_signatures_disagree(self):
    self.check_error("""
      class A(object):
          @staticmethod
          def foo(x: int): ...
          @classmethod
          def foo(x: str): ...
      """, 1, "Overloaded signatures for foo disagree on decorators")

  def test_classmethod(self):
    ast = self.check("""
      class A:
          @classmethod
          def foo(x: int) -> str: ...
      """)
    self.assertEqual("classmethod", ast.classes[0].methods[0].kind)

  def test_staticmethod(self):
    ast = self.check("""
      class A:
          @staticmethod
          def foo(x: int) -> str: ...
      """)
    self.assertEqual("staticmethod", ast.classes[0].methods[0].kind)

  def test_new(self):
    ast = self.check("""
      class A:
          def __new__(self) -> A: ...
      """)
    self.assertEqual("staticmethod", ast.classes[0].methods[0].kind)

  def test_abstractmethod(self):
    ast = self.check("""
      class A:
          @abstractmethod
          def foo(x: int) -> str: ...
      """)
    self.assertEqual("method", ast.Lookup("A").Lookup("foo").kind)
    self.assertEqual(True, ast.Lookup("A").Lookup("foo").is_abstract)

  def test_abstractmethod_manysignatures(self):
    ast = self.check("""
      class A:
          @abstractmethod
          def foo(x: int) -> str: ...
          @abstractmethod
          def foo(x: int, y: int) -> str: ...
          @abstractmethod
          def foo(x: int, y: int, z: int) -> str: ...
      """, """
      class A:
          @abstractmethod
          @overload
          def foo(x: int) -> str: ...
          @abstractmethod
          @overload
          def foo(x: int, y: int) -> str: ...
          @abstractmethod
          @overload
          def foo(x: int, y: int, z: int) -> str: ...
      """)
    self.assertEqual("method", ast.Lookup("A").Lookup("foo").kind)
    self.assertEqual(True, ast.Lookup("A").Lookup("foo").is_abstract)

  def test_abstractmethod_conflict(self):
    self.check_error("""
      class A(object):
          @abstractmethod
          def foo(x: int) -> str: ...
          def foo(x: int, y: int) -> str: ...
      """, 1, "Overloaded signatures for foo disagree on "
                     "abstractmethod decorators")


class EntireFileTest(_ParserTestBase):

  def test_builtins(self):
    self.check(get_builtins_source(self.python_version), expected=IGNORE)


class AnyTest(_ParserTestBase):

  def test_generic_any(self):
    self.check("""
      from typing import Any
      x = ...  # type: Any[int]""",
               """
      from typing import Any

      x: Any""")

  def test_generic_any_alias(self):
    self.check("""
      from typing import Any
      Foo = Any
      Bar = Foo[int]
      x = ...  # type: Bar[int, str]""",
               """
      from typing import Any

      Foo = Any
      Bar = Any

      x: Any""")


class CanonicalPyiTest(_ParserTestBase):

  def test_canonical_version(self):
    src = textwrap.dedent("""
        from typing import Any
        def foo(x: int = 0) -> Any: ...
        def foo(x: str) -> Any: ...
    """)
    expected = textwrap.dedent("""
        from typing import Any

        @overload
        def foo(x: int = ...) -> Any: ...
        @overload
        def foo(x: str) -> Any: ...
    """).strip()
    self.assertMultiLineEqual(
        parser.canonical_pyi(src, self.python_version), expected)


class TypeMacroTest(_ParserTestBase):

  def test_simple(self):
    self.check("""
      from typing import List, TypeVar
      Alias = List[List[T]]
      T = TypeVar('T')
      S = TypeVar('S')
      def f(x: Alias[S]) -> S: ...
      def g(x: Alias[str]) -> str: ...""", """
      from typing import List, TypeVar

      Alias = List[List[T]]

      S = TypeVar('S')
      T = TypeVar('T')

      def f(x: List[List[S]]) -> S: ...
      def g(x: List[List[str]]) -> str: ...""")

  def test_partial_replacement(self):
    self.check("""
      from typing import Dict, TypeVar
      DictAlias = Dict[int, V]
      V = TypeVar('V')
      def f(x: DictAlias[str]) -> None: ...""", """
      from typing import Dict, TypeVar

      DictAlias = Dict[int, V]

      V = TypeVar('V')

      def f(x: Dict[int, str]) -> None: ...""")

  def test_multiple_parameters(self):
    self.check("""
      from typing import Dict, List, TypeVar
      Alias = List[Dict[K, V]]
      K = TypeVar('K')
      V = TypeVar('V')
      def f(x: Alias[K, V]) -> Dict[K, V]: ...""", """
      from typing import Dict, List, TypeVar

      Alias = List[Dict[K, V]]

      K = TypeVar('K')
      V = TypeVar('V')

      def f(x: List[Dict[K, V]]) -> Dict[K, V]: ...""")

  def test_no_parameters(self):
    self.check("""
      from typing import List, TypeVar
      Alias = List[List[T]]
      T = TypeVar('T')
      def f(x: Alias) -> None: ...""", """
      from typing import Any, List, TypeVar

      Alias = List[List[T]]

      T = TypeVar('T')

      def f(x: List[List[Any]]) -> None: ...""")

  def test_union(self):
    self.check("""
      from typing import List, TypeVar, Union
      Alias = Union[List[T], List[S]]
      T = TypeVar('T')
      S = TypeVar('S')
      def f(x: Alias[S, T]) -> Union[S, T]: ...""", """
      from typing import List, TypeVar, Union

      Alias = Union[List[T], List[S]]

      S = TypeVar('S')
      T = TypeVar('T')

      def f(x: Union[List[S], List[T]]) -> Union[S, T]: ...""")

  def test_repeated_type_parameter(self):
    self.check("""
      from typing import Dict, TypeVar
      Alias = Dict[T, T]
      T = TypeVar('T')
      def f(x: Alias[str]) -> None: ...""", """
      from typing import Dict, TypeVar

      Alias = Dict[T, T]

      T = TypeVar('T')

      def f(x: Dict[str, str]) -> None: ...""")

  def test_wrong_parameter_count(self):
    self.check_error("""
      from typing import List, TypeVar
      Alias = List[List[T]]
      T = TypeVar('T')
      def f(x: Alias[T, T]) -> T: ...
    """, 4, "List[List[T]] expected 1 parameters, got 2")

  def test_anystr(self):
    self.check("""
      from typing import AnyStr, List
      Alias = List[AnyStr]
      def f(x: Alias[str]) -> None: ...
    """, """
      from typing import AnyStr, List

      Alias = List[AnyStr]

      def f(x: List[str]) -> None: ...
    """)


class ImportTypeIgnoreTest(_ParserTestBase):

  def test_import(self):
    self.check("""
      import mod  # type: ignore
      def f(x: mod.attr) -> None: ...
    """, """
      import mod

      def f(x: mod.attr) -> None: ...""")

  def test_from_import(self):
    src = textwrap.dedent("""
      from mod import attr  # type: ignore
      def f(x: attr) -> None: ...
    """)
    ast = parser.parse_string(src, python_version=self.python_version)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))

  def test_relative_import(self):
    src = textwrap.dedent("""
      from . import attr  # type: ignore
      def f(x: attr) -> None: ...
    """)
    ast = parser.parse_string(src, python_version=self.python_version)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))

  def test_relative_import_parent(self):
    src = textwrap.dedent("""
      from .. import attr  # type: ignore
      def f(x: attr) -> None: ...
    """)
    ast = parser.parse_string(src, python_version=self.python_version)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))


class LiteralTest(_ParserTestBase):

  def test_bool(self):
    self.check("""
      from typing import Literal

      x: Literal[False]
      y: Literal[True]
    """)

  def test_int(self):
    self.check("""
      from typing import Literal

      x: Literal[42]
    """)

  def test_string(self):
    self.check("""
      from typing import Literal

      x: Literal["x"]
      y: Literal[""]
    """)

  def test_bytestring(self):
    self.check("""
      from typing import Literal

      x: Literal[b""]
      y: Literal[b'']
      z: Literal[b"xyz"]
    """)

  def test_unicodestring(self):
    self.check("""
      from typing import Literal

      x: Literal[u""]
      y: Literal[u'']
      z: Literal[u"xyz"]
    """)

  def test_none(self):
    self.check("""
      from typing import Literal

      x: Literal[None]
    """, "x: None")

  def test_enum(self):
    # TODO(b/123775699): support enums.
    self.check("""
      import enum
      from typing import Literal

      x: Literal[Color.RED]

      class Color(enum.Enum):
          RED: str
    """, """
      import enum
      from typing import Any

      x: Any

      class Color(enum.Enum):
          RED: str
    """)

  def test_multiple_parameters(self):
    self.check("""
      from typing import Literal

      x: Literal[True, 0, b"", u"", None]
    """, """
      from typing import Literal, Optional, Union

      x: Optional[Union[Literal[True], Literal[0], Literal[b""], Literal[u""]]]
    """)

  def test_stray_number(self):
    self.check_error("""
      from typing import Tuple

      x: Tuple[int, int, 0, int]
    """, 3, "Tuple[_, _, 0, _] not supported")

  def test_stray_string(self):
    self.check_error("""
      from typing import Tuple

      x: Tuple[str, str, '', str]
    """, 3, "Tuple[_, _, '', _] not supported")

  def test_stray_bytestring(self):
    self.check_error("""
      from typing import Tuple

      x: Tuple[str, b'', str, str]
    """, 3, "Tuple[_, b'', _, _] not supported")

  def test_stray_unicodestring(self):
    self.check_error("""
      from typing import Tuple

      x: Tuple[str, u'', str, str]
    """, 3, "Tuple[_, u'', _, _] not supported")

  def test_typing_extensions(self):
    self.check("""
      from typing_extensions import Literal

      x: Literal[42]
    """)


if __name__ == "__main__":
  unittest.main()
