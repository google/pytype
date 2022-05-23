import hashlib
import sys
import textwrap

from pytype.pyi import parser
from pytype.pyi import parser_test_base
from pytype.pytd import pytd
from pytype.tests import test_base
from pytype.tests import test_utils

import unittest


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


class ParserTest(parser_test_base.ParserTestBase):

  def test_syntax_error(self):
    self.check_error("123", 1, "Unexpected expression")

  def test_illegal_character(self):
    self.check_error("^", 1, "invalid syntax")

  def test_invalid_indentation(self):
    self.check_error("""
      class Foo:
        x = ... # type: int
       y""", 3, "unindent does not match")

  @unittest.skip("New parser does not support this")
  def test_type_on_next_line(self):
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

  @unittest.skip("Not checking invalid literals")
  def test_invalid_constant(self):
    self.check_error("x = 123", 1,
                     "Only '0' allowed as int literal")
    self.check("x = 0.0", "x: float")
    self.check_error("x = 12.3", 1,
                     "Only '0.0' allowed as float literal")

  @test_utils.skipFromPy((3, 8), "No longer tagging strings 'unicode'")
  def test_string_constant_37(self):
    self.check("x = b''", "x: bytes")
    self.check("x = u''", "x: unicode")
    self.check('x = b""', "x: bytes")
    self.check('x = u""', "x: unicode")
    self.check("x = ''", "x: str")
    self.check('x = ""', "x: str")

  @test_utils.skipBeforePy((3, 8), "No longer tagging strings 'unicode'")
  def test_string_constant_38(self):
    self.check("x = b''", "x: bytes")
    self.check("x = u''", "x: str")
    self.check('x = b""', "x: bytes")
    self.check('x = u""', "x: str")
    self.check("x = ''", "x: str")
    self.check('x = ""', "x: str")

  @unittest.skip("We allow all strings.")
  def test_invalid_string_constant(self):
    self.check_error("x = b'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")
    self.check_error("x = u'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")
    self.check_error("x = 'x'", 1,
                     "Only '', b'', and u'' allowed as string literals")

  def test_constant_pep526(self):
    self.check("x : str", "x: str")
    self.check("x : str = ...", "x: str = ...")

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
          def x(self) -> int: ...
          y = x
          z = y
          @classmethod
          def a(cls) -> str: ...
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

  def test_chained_assignment(self):
    self.check("""
      a = b = int
    """, """
      a = int
      b = int
    """)

  def test_multiple_assignment(self):
    self.check("""
      a, b = int, str
    """, """
      a = int
      b = str
    """)
    self.check("""
      (a, b) = (c, d) = int, str
    """, """
      a = int
      b = str
      c = int
      d = str
    """)

  def test_invalid_multiple_assignment(self):
    self.check_error("""
      a, b = int, str, bool
    """, 1, "Cannot unpack 2 values for multiple assignment")
    self.check_error("""
      a, b = int
    """, 1, "Cannot unpack 2 values for multiple assignment")

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
    """, 2, "invalid syntax")
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
    self.check("import foo.bar.baz")
    self.check("import a as b")
    self.check("from foo.bar import baz")
    self.check("from foo.bar import baz as abc")
    self.check("from typing import NamedTuple, TypeVar", "")
    self.check("from foo.bar import *")
    self.check_error("from foo import * as bar", 1, "invalid syntax")
    self.check("from foo import a, b",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b)",
               "from foo import a\nfrom foo import b")
    self.check("from foo import (a, b, )",
               "from foo import a\nfrom foo import b")

  def test_from_import(self):
    ast = self.check("from foo import c\nclass Bar(c.X): ...",
                     parser_test_base.IGNORE)
    base, = ast.Lookup("Bar").bases
    self.assertEqual(base, pytd.NamedType("foo.c.X"))

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
      from typing import overload

      @overload
      def foo(x: int) -> int: ...
      @overload
      def foo(x: str) -> str: ...""")
    # @overload decorators should be properly round-tripped.
    self.check("""
      @overload
      def foo(x: int) -> int: ...
      @overload
      def foo(x: str) -> str: ...""", """
      from typing import overload

      @overload
      def foo(x: int) -> int: ...
      @overload
      def foo(x: str) -> str: ...""")

  def test_type(self):
    self.check("x: str")
    self.check("x = ...  # type: (str)", "x: str")
    self.check("x: foo.bar.Baz", prologue="import foo.bar")
    self.check("x: nothing")

  @unittest.skip("TODO: add errors for these")
  def test_deprecated_type(self):
    self.check_error("x = ...  # type: int and str and float",
                     1, "invalid syntax")
    self.check_error("x = ...  # type: ?", 1, "invalid syntax")
    self.check("x = ...  # type: int or str or float",
               1, "invalid syntax")

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

  def test_external_alias(self):
    self.check("""
      from somewhere import Foo

      class Bar:
          Baz = Foo
    """, """
      from somewhere import Foo
      from typing import Any

      class Bar:
          Baz: Any
    """)

  def test_same_named_alias(self):
    self.check("""
      import somewhere
      class Bar:
          Foo = somewhere.Foo
    """, """
      import somewhere
      from typing import Any

      class Bar:
          Foo: Any
    """)

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
    self.check_error("T = TypeVar()", 1, "Missing arguments to TypeVar")
    self.check_error("T = TypeVar(*args)", 1, "Bad arguments to TypeVar")
    self.check_error("T = TypeVar(...)", 1, "Bad arguments to TypeVar")
    self.check_error("T = TypeVar('Q')", 1,
                     "TypeVar name needs to be 'Q' (not 'T')")
    self.check_error("T = TypeVar('T', covariant=True, int, float)", 1,
                     "positional argument follows keyword argument")
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

  def test_typing_typevar(self):
    self.check("""
      import typing
      T = typing.TypeVar('T')
    """, """
      import typing
      from typing import TypeVar

      T = TypeVar('T')
    """)

  def test_error_formatting(self):
    src = """
      class Foo:
        this is not valid"""
    with self.assertRaises(parser.ParseError) as e:
      parser.parse_string(textwrap.dedent(src).lstrip(), filename="foo.py",
                          options=self.options)
    self.assertMultiLineEqual(textwrap.dedent("""
        File: "foo.py", line 2
          this is not valid
         ^
      ParseError: Unexpected expression
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
        X = ... # type: Any
      y = bar.X.Baz
      z = X.Baz
    """), name="foo", options=self.options)
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

  def test_all(self):
    self.check("""
      __all__ = ['a']
    """, """
      from typing import List

      __all__: List[str] = ...
    """)

  def test_invalid_constructor(self):
    e = "Constructors and function calls in type annotations are not supported."
    self.check_error("""
      x = ... # type: typing.NamedTuple("A", [])
    """, 1, e)

    self.check_error("""
      x: typing.NamedTuple("A", []) = ...
    """, 1, e)

  def test_match_args(self):
    self.check("""
      from typing import Final

      class A:
          __match_args__ = ("a", "b")

      class B:
          __match_args__: Final = ("a", "b")
    """, """
      class A:
          __match_args__: tuple

      class B:
          __match_args__: tuple
    """)


class QuotedTypeTest(parser_test_base.ParserTestBase):

  def test_annotation(self):
    self.check("""
      class A: ...
      x: "A"
      y: "List[A]" = ...
    """, """
      x: A
      y: List[A] = ...

      class A: ...
    """)

  def test_def(self):
    self.check("""
      def f(x: "int") -> "str": ...
    """, """
      def f(x: int) -> str: ...
    """)


class HomogeneousTypeTest(parser_test_base.ParserTestBase):

  def test_callable_parameters(self):
    self.check("""
      from typing import Callable

      x: Callable[[int, str], bool]""")
    self.check("""
      from typing import Callable

      x = ...  # type: Callable[..., bool]""", """
      from typing import Callable

      x: Callable[..., bool]""")
    self.check("""
      from typing import Any, Callable

      x: Callable[Any, bool]""", """
      from typing import Callable

      x: Callable[..., bool]""")
    self.check("""
      from typing import Any, Callable

      x: Callable[[Any], bool]""")
    self.check("""
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


class NamedTupleTest(parser_test_base.ParserTestBase):

  def test_assign_namedtuple(self):
    self.check("X = NamedTuple('X', [])", """
      from typing import NamedTuple

      X = namedtuple_X_0

      class namedtuple_X_0(NamedTuple): ...
    """)

  def test_subclass_namedtuple(self):
    self.check("""
      from typing import NamedTuple
      class X(NamedTuple('X', [])): ...
    """, """
      from typing import NamedTuple

      class namedtuple_X_0(NamedTuple): ...

      class X(namedtuple_X_0): ...
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
      from typing import NamedTuple

      Foo = namedtuple_Foo_0

      class namedtuple_Foo_0(NamedTuple):
          a: int
          b: str
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
      from collections import namedtuple
      from typing import Any, NamedTuple

      Foo = namedtuple_Foo_0

      class namedtuple_Foo_0(NamedTuple):
          a: Any
          b: Any
    """)

  def test_collections_namedtuple(self):
    expected = """
      from collections import namedtuple
      from typing import Any, NamedTuple

      X = namedtuple_X_0

      class namedtuple_X_0(NamedTuple):
          y: Any
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
      from typing import NamedTuple

      class X(NamedTuple):
          y: int
          z: str
    """)

  def test_typing_namedtuple_class_with_method(self):
    self.check("""
      from typing import NamedTuple
      class X(NamedTuple):
        y: int
        z: str
        def foo(self) -> None: ...
    """, """
      from typing import NamedTuple

      class X(NamedTuple):
          y: int
          z: str
          def foo(self) -> None: ...
    """)

  def test_typing_namedtuple_class_multi_inheritance(self):
    self.check("""
      from typing import NamedTuple
      class X(dict, NamedTuple):
        y: int
        z: str
    """, """
      from typing import NamedTuple

      class X(dict, NamedTuple):
          y: int
          z: str
    """)

  def test_multi_namedtuple_base(self):
    self.check_error("""
      from typing import NamedTuple
      class X(NamedTuple, NamedTuple): ...
    """, 2, "cannot inherit from bare NamedTuple more than once")

  def test_redefine_namedtuple(self):
    self.check("""
      class NamedTuple: ...
    """)


class FunctionTest(parser_test_base.ParserTestBase):

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
    self.check("def foo(x: int, y: str, z: bool,) -> int: ...",
               "def foo(x: int, y: str, z: bool) -> int: ...")

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
                     "named arguments must follow bare *")
    self.check_error("def foo(*x, *y) -> int: ...", 1, "invalid syntax")
    self.check_error("def foo(**x, *y) -> int: ...", 1, "invalid syntax")

  @unittest.skip("New parser does not support this syntax")
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
          bar: str = ...
    """)
    self.check("""
      def f(  # type: ignore
        x: int) -> None: ...
    """, """
      def f(x: int) -> None: ...
    """)

  def test_typeignore_alias(self):
    self.check("""
      class Foo:
          def f(self) -> None: ...
          g = f  # type: ignore
    """, """
      class Foo:
          def f(self) -> None: ...
          def g(self) -> None: ...
    """)

  def test_typeignore_slots(self):
    self.check("""
      class Foo:
          __slots__ = ["a", "b"]  # type: ignore
    """, """
      class Foo:
          __slots__ = ["a", "b"]
    """)

  def test_typeignore_errorcode(self):
    self.check("""
      def f() -> None: ...  # type: ignore[override]
      def g() -> None: ...  # type: ignore[var-annotated]
      def h() -> None: ...  # type: ignore[abstract, no-untyped-def]
    """, """
      def f() -> None: ...
      def g() -> None: ...
      def h() -> None: ...
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
      from typing import overload

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
      from typing import overload

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
      def foo(self) -> int: ...""",
                     None,
                     "Module-level functions with property decorators: foo")

    self.check_error("""
      @foo.setter
      def foo(self, x) -> int: ...""",
                     None,
                     "Module-level functions with property decorators: foo")

    line = 1 if sys.version_info < (3, 8) else 3
    self.check_error("""
      @classmethod
      @staticmethod
      def foo() -> int: ...""",
                     line,
                     "Too many decorators for foo")

  def test_module_getattr(self):
    self.check("""
      def __getattr__(name) -> int: ...
    """)

    self.check_error("""
      def __getattr__(name) -> int: ...
      def __getattr__(name) -> str: ...
    """, None, "Multiple signatures for module __getattr__")

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

  def test_decorated_class(self):
    self.check("""
      @decorator
      class Foo: ...
    """)

  def test_multiple_class_decorators(self):
    self.check("""
      @decorator1
      @decorator2
      class Foo: ...
    """)

  def test_bad_decorated_class(self):
    line = 1 if sys.version_info < (3, 8) else 2
    self.check_error("""
      @classmethod
      class Foo: ...
    """, line, "Unsupported class decorators: classmethod")

  def test_dataclass_decorator(self):
    self.check("""
      from dataclasses import dataclass

      @dataclass
      class Foo:
          x: int
          y: str = ...
    """)

  def test_dataclass_default_error(self):
    self.check_error("""
      from dataclasses import dataclass
      @dataclass
      class Foo:
        x: int = ...
        y: str
    """, None, "non-default argument y follows default argument x")

  def test_empty_body(self):
    self.check("def foo() -> int: ...")
    self.check("def foo() -> int: ...",
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
          y = int""", 1, "No parameter named 'y'")

  def test_mutator_from_annotation(self):
    self.check("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
          def __init__(self: Foo[str]) -> None: ...
    """, """
      from typing import Generic, TypeVar

      T = TypeVar('T')

      class Foo(Generic[T]):
          def __init__(self) -> None:
              self = Foo[str]
    """)

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

  def test_invalid_body(self):
    self.check_error("""
      def foo(x) -> int:
        a: str""", 1, "Unexpected statement in function body")

  def test_return(self):
    self.check("def foo() -> int: ...")
    self.check("def foo(): ...",
               "def foo() -> Any: ...",
               prologue="from typing import Any")

  def test_async(self):
    self.check("async def foo() -> int: ...",
               "def foo() -> Coroutine[Any, Any, int]: ...",
               prologue="from typing import Any, Coroutine")


class ClassTest(parser_test_base.ParserTestBase):

  def test_no_bases(self):
    canonical = """
      class Foo: ...
      """

    self.check(canonical, canonical)
    self.check("""
      class Foo():
          pass
      """, canonical)

  def test_bases(self):
    self.check("""
      class Foo(Bar): ...
    """)
    self.check("""
      class Foo(Bar, Baz): ...
      """)

  def test_base_remove_nothingtype(self):
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
      """, 1, "Unexpected classdef kwarg 'badkeyword'")
    if sys.version_info[:2] >= (3, 10):
      expected_msg = "expected ':'"
    else:
      expected_msg = "positional argument follows keyword argument"
    self.check_error("""
      class Foo(metaclass=Meta, Bar): ...
      """, 1, expected_msg)

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
          def a(self) -> int: ...
      """, """
      from typing import Annotated

      class Foo:
          a: Annotated[int, 'property']
      """)

  def test_duplicate_name(self):
    self.check_error("""
      class Foo:
          bar = ...  # type: int
          bar = ...  # type: str
      """, 1, "Duplicate class-level identifier(s): bar")
    self.check_error("""
      class Foo:
          def bar(self) -> int: ...
          bar = ...  # type: str
      """, 1, "Duplicate class-level identifier(s): bar")
    # Multiple method defs are ok (needed for variant signatures).
    self.check("""
      class Foo:
          @overload
          def x(self) -> int: ...
          @overload
          def x(self) -> str: ...
      """, """
      from typing import overload

      class Foo:
          @overload
          def x(self) -> int: ...
          @overload
          def x(self) -> str: ...
      """)

  def test_protocol_base(self):
    self.check("""
      from typing import Protocol

      class Foo(Protocol): ...
    """)

  def test_parameterized_protocol_base(self):
    self.check("""
      from typing import Protocol, TypeVar

      T = TypeVar('T')

      class Foo(Protocol[T]): ...
    """, """
      from typing import Generic, Protocol, TypeVar

      T = TypeVar('T')

      class Foo(Protocol, Generic[T]): ...
    """)

  def test_typing_extensions_parameterized_protocol(self):
    self.check("""
      from typing import TypeVar
      from typing_extensions import Protocol

      T = TypeVar('T')

      class Foo(Protocol[T]): ...
    """, """
      import typing
      from typing import Generic, TypeVar
      from typing_extensions import Protocol

      T = TypeVar('T')

      class Foo(typing.Protocol, Generic[T]): ...
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

  def test_nested_class_typing_class_conflict(self):
    ast = parser.parse_string(textwrap.dedent("""
      from typing import Mapping
      class Foo:
        class Mapping: ...
      x: Mapping
    """).lstrip())
    x = ast.Lookup("x")
    self.assertEqual(x.type.name, "typing.Mapping")


class IfTest(parser_test_base.ParserTestBase):

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


class ClassIfTest(parser_test_base.ParserTestBase):

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
    """, 3, "Import statements need to be at module level")

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
    """, 3, r"TypeVars need to be defined at module level")


class ConditionTest(parser_test_base.ParserTestBase):

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


class PropertyDecoratorTest(parser_test_base.ParserTestBase):
  """Tests that cover _parse_signature_as_property()."""

  def test_property_with_type(self):
    expected = """
      from typing import Annotated

      class A:
          name: Annotated[str, 'property']
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
      from typing import Annotated, Any

      class A:
          name: Annotated[Any, 'property']
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
          from typing import Annotated, Any

          class A:
              name: Annotated[Any, 'property']
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
    line = 1 if sys.version_info < (3, 8) else 2
    self.check_error("""
      class A:
          @property
          def name(self, bad_arg): ...
      """, 1, "@property needs 1 param(s), got 2")

    self.check_error("""
      class A:
          @name.setter
          def name(self): ...
      """, 1, "@name.setter needs 2 param(s), got 1")

    line = 2 if sys.version_info < (3, 8) else 4
    self.check_error("""
      class A:
          @property
          @staticmethod
          def name(self): ...
      """, line, "Too many decorators for name")

    self.check_error("""
      @property
      def name(self): ...
      """, None, "Module-level functions with property decorators: name")

  def test_property_clash(self):
    self.check_error("""
      class A:
          @property
          def name(self) -> str: ...

          @property
          def name(self) -> int: ...
      """, 1, "Invalid property decorators for method `name`")

  def test_abstract_property(self):
    self.check("""
      class Foo:
        @property
        @abstractmethod
        def x(self) -> int: ...
        @x.setter
        def x(self, y: int) -> None: ...
    """, """
      from typing import Annotated

      class Foo:
          x: Annotated[int, 'property']
    """)


class MergeSignaturesTest(parser_test_base.ParserTestBase):

  def test_property(self):
    self.check("""
      class A:
          @property
          def name(self) -> str: ...
      """, """
      from typing import Annotated

      class A:
          name: Annotated[str, 'property']
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
      from typing import overload

      @overload
      def foo(x: int) -> str: ...
      @overload
      def foo(x: str) -> str: ...""")
    self.assertEqual(len(ast.functions), 1)
    foo = ast.functions[0]
    self.assertEqual(len(foo.signatures), 2)

  def test_method_and_property_error(self):
    self.check_error("""
      class A:
          @property
          def name(self): ...

          def name(self): ...
      """, 1, "Overloaded signatures for name disagree on decorators")

  def test_overloaded_signatures_disagree(self):
    self.check_error("""
      class A:
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
    self.assertEqual(pytd.MethodKind.CLASSMETHOD,
                     ast.classes[0].methods[0].kind)

  def test_staticmethod(self):
    ast = self.check("""
      class A:
          @staticmethod
          def foo(x: int) -> str: ...
      """)
    self.assertEqual(pytd.MethodKind.STATICMETHOD,
                     ast.classes[0].methods[0].kind)

  def test_new(self):
    ast = self.check("""
      class A:
          def __new__(self) -> A: ...
      """)
    self.assertEqual(pytd.MethodKind.STATICMETHOD,
                     ast.classes[0].methods[0].kind)

  def test_abstractmethod(self):
    ast = self.check("""
      class A:
          @abstractmethod
          def foo(x: int) -> str: ...
      """)
    self.assertEqual(pytd.MethodKind.METHOD, ast.Lookup("A").Lookup("foo").kind)
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
      from typing import overload

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
    self.assertEqual(pytd.MethodKind.METHOD, ast.Lookup("A").Lookup("foo").kind)
    self.assertEqual(True, ast.Lookup("A").Lookup("foo").is_abstract)

  def test_abstractmethod_conflict(self):
    self.check_error("""
      class A:
          @abstractmethod
          def foo(x: int) -> str: ...
          def foo(x: int, y: int) -> str: ...
      """, 1, "Overloaded signatures for foo disagree on "
                     "abstractmethod decorators")


class AnyTest(parser_test_base.ParserTestBase):

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


class CanonicalPyiTest(parser_test_base.ParserTestBase):

  def test_canonical_version(self):
    src = textwrap.dedent("""
        from typing import Any
        def foo(x: int = 0) -> Any: ...
        def foo(x: str) -> Any: ...
    """)
    expected = textwrap.dedent("""
        from typing import Any, overload

        @overload
        def foo(x: int = ...) -> Any: ...
        @overload
        def foo(x: str) -> Any: ...
    """).strip()
    self.assertMultiLineEqual(
        parser.canonical_pyi(src, options=self.options), expected)


class TypeMacroTest(parser_test_base.ParserTestBase):

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


class ImportTypeIgnoreTest(parser_test_base.ParserTestBase):

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
    ast = parser.parse_string(src, options=self.options)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))

  def test_relative_import(self):
    src = textwrap.dedent("""
      from . import attr  # type: ignore
      def f(x: attr) -> None: ...
    """)
    ast = parser.parse_string(src, options=self.options)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))

  def test_relative_import_parent(self):
    src = textwrap.dedent("""
      from .. import attr  # type: ignore
      def f(x: attr) -> None: ...
    """)
    ast = parser.parse_string(src, options=self.options)
    self.assertTrue(ast.Lookup("attr"))
    self.assertTrue(ast.Lookup("f"))


class LiteralTest(parser_test_base.ParserTestBase):

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

      x: Literal['x']
      y: Literal['']
    """)

  def test_bytestring(self):
    self.check("""
      from typing import Literal

      x: Literal[b'']
      y: Literal[b'']
      z: Literal[b'xyz']
    """)

  @test_utils.skipFromPy((3, 8), "No longer tagging strings 'unicode'")
  def test_unicodestring(self):
    self.check("""
      from typing import Literal

      y: Literal[u'']
      z: Literal[u'xyz']
    """)

  def test_none(self):
    self.check("""
      from typing import Literal

      x: Literal[None]
    """, "x: None")

  def test_enum(self):
    self.check("""
      import enum
      from typing import Literal

      x: Literal[Color.RED]

      class Color(enum.Enum):
          RED: str
    """)

  def test_multiple_parameters(self):
    self.check("""
      from typing import Literal

      x: Literal[True, 0, b"", "", None]
    """, """
      from typing import Literal, Optional

      x: Optional[Literal[True, 0, b'', '']]
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

  @test_utils.skipFromPy((3, 8), "No longer tagging strings 'unicode'")
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

  def test_unnest(self):
    self.check("""
      from typing import Literal
      MyLiteralAlias = Literal[42]
      x: Literal[MyLiteralAlias, Literal[Literal[True]], None]
      y: Literal[1, Literal[2, Literal[3]]]
    """, """
      from typing import Literal, Optional

      MyLiteralAlias = Literal[42]

      x: Optional[Literal[42, True]]
      y: Literal[1, 2, 3]
    """)

  def test_bad_value(self):
    self.check_error("""
      from typing import Literal
      x: Literal[0.0]
    """, 2, "Invalid type `float` in Literal[0.0].")

  def test_forbid_expressions(self):
    msg = "Expressions are not allowed in typing.Literal."
    self.check_error("""
      from typing import Literal
      x: Literal[3+4]
    """, 2, msg)
    self.check_error("""
      from typing_extensions import Literal
      x: Literal[3+4]
    """, 2, msg)
    self.check_error("""
      import typing
      x: typing.Literal[3+4]
    """, 2, msg)
    self.check_error("""
      import typing_extensions
      x: typing_extensions.Literal[3+4]
    """, 2, msg)

  def test_final_literals(self):
    # See https://github.com/python/typeshed/issues/7258 for context.
    self.check("""
      import enum
      from typing_extensions import Final

      class Color(enum.Enum):
        RED: str

      x1: Final = 3
      x2: Final = True
      x3: Final = 'x3'
      x4: Final = b'x4'
      x5: Final = None
      x6: Final = Color.RED
    """, """
      import enum
      from typing import Literal
      from typing_extensions import Final

      x1: Literal[3]
      x2: Literal[True]
      x3: Literal['x3']
      x4: Literal[b'x4']
      x5: Literal[None]
      x6: Literal[Color.RED]

      class Color(enum.Enum):
          RED: str
    """)

  def test_final_non_literal(self):
    self.check("""
      from typing_extensions import Final
      x: Final
      y: Final = ...
    """, """
      import typing_extensions
      from typing_extensions import Final

      x: typing_extensions.Final
      y: typing_extensions.Final = ...
    """)

  def test_bad_final_literal(self):
    msg = ("Default value for x: Final can only be '...' or a legal Literal "
           "parameter, got LITERAL(3.14)")
    self.check_error("""
      from typing_extensions import Final
      x: Final = 3.14
    """, 2, msg)


class TypedDictTest(parser_test_base.ParserTestBase):

  def test_assign(self):
    self.check("""
      from typing_extensions import TypedDict
      X = TypedDict('X', {})
    """, """
      from typing import Any, Dict
      from typing_extensions import TypedDict

      X = Dict[str, Any]
    """)

  def test_assign_with_items(self):
    self.check("""
      from typing_extensions import TypedDict
      X = TypedDict('X', {'a': int, 'b': str})
    """, """
      from typing import Any, Dict
      from typing_extensions import TypedDict

      X = Dict[str, Any]
    """)

  def test_assign_with_kwarg(self):
    self.check("""
      from typing_extensions import TypedDict
      X = TypedDict('X', {}, total=False)
    """, """
      from typing import Any, Dict
      from typing_extensions import TypedDict

      X = Dict[str, Any]
    """)

  def test_trailing_comma(self):
    self.check("""
      from typing_extensions import TypedDict
      X = TypedDict('X', {
          'a': int,
          'b': str,
      },)
    """, """
      from typing import Any, Dict
      from typing_extensions import TypedDict

      X = Dict[str, Any]
    """)

  def test_kwarg(self):
    self.check("""
      from typing import TypedDict

      class Foo(TypedDict, total=False): ...
    """, """
      from typing import TypedDict

      class Foo(TypedDict): ...
    """)

  def test_typing_extensions(self):
    self.check("""
      from typing_extensions import TypedDict

      class Foo(TypedDict, total=False): ...
    """, """
      import typing_extensions
      from typing_extensions import TypedDict

      class Foo(typing_extensions.TypedDict): ...
    """)

  def test_multiple_classdef_kwargs(self):
    self.check("""
      from typing import TypedDict

      class Foo(TypedDict, total=False, metaclass=Meta): ...
    """, """
      from typing import TypedDict

      class Foo(TypedDict, metaclass=Meta): ...
    """)

  def test_total_in_subclass(self):
    self.check("""
      from typing import TypedDict
      class Foo(TypedDict):
          x: str
      class Bar(Foo, total=False):
          y: int
    """, """
      from typing import TypedDict

      class Foo(TypedDict):
          x: str

      class Bar(Foo):
          y: int
    """)


class NewTypeTest(parser_test_base.ParserTestBase):

  def test_basic(self):
    self.check("""
      from typing import NewType
      X = NewType('X', int)
    """, """
      X = newtype_X_0

      class newtype_X_0(int):
          def __init__(self, val: int) -> None: ...
    """)

  def test_fullname(self):
    self.check("""
      import typing
      X = typing.NewType('X', int)
    """, """
      import typing

      X = newtype_X_0

      class newtype_X_0(int):
          def __init__(self, val: int) -> None: ...
    """)


class MethodAliasTest(parser_test_base.ParserTestBase):

  def test_normal_method(self):
    self.check("""
      class Foo:
          def f(self, x: int) -> None: ...
      _foo: Foo
      f1 = Foo.f
      f2 = _foo.f
    """, """
      _foo: Foo

      class Foo:
          def f(self, x: int) -> None: ...

      def f1(self, x: int) -> None: ...
      def f2(x: int) -> None: ...
    """)

  def test_classmethod(self):
    self.check("""
      class Foo:
          @classmethod
          def f(cls, x: int) -> None: ...
      _foo: Foo
      f1 = Foo.f
      f2 = _foo.f
    """, """
      _foo: Foo

      class Foo:
          @classmethod
          def f(cls, x: int) -> None: ...

      def f1(x: int) -> None: ...
      def f2(x: int) -> None: ...
    """)

  def test_staticmethod(self):
    self.check("""
      class Foo:
          @staticmethod
          def f(x: int) -> None: ...
      _foo: Foo
      f1 = Foo.f
      f2 = _foo.f
    """, """
      _foo: Foo

      class Foo:
          @staticmethod
          def f(x: int) -> None: ...

      def f1(x: int) -> None: ...
      def f2(x: int) -> None: ...
    """)

  def test_nested_constant(self):
    self.check("""
      class Foo:
          foo: Foo
          def f(self, x: int) -> None: ...
      f = Foo.foo.f
    """, """
      class Foo:
          foo: Foo
          def f(self, x: int) -> None: ...

      def f(x: int) -> None: ...
    """)


class AnnotatedTest(parser_test_base.ParserTestBase):
  """Test typing.Annotated."""

  def test_annotated(self):
    self.check("""
      from typing import Annotated

      class Foo:
          x: Annotated[int, 'a', 'b', 'c']
    """)

  def test_annotated_from_extensions(self):
    self.check("""
      from typing_extensions import Annotated

      class Foo:
          x: Annotated[int, 'a', 'b', 'c']
    """)

  def test_dict(self):
    self.check("""
      from typing_extensions import Annotated

      class Foo:
          x: Annotated[int, {'a': 'A', 'b': True, 'c': Foo}]
    """, """
      from typing_extensions import Annotated

      class Foo:
          x: Annotated[int, {'a': 'A', 'b': True, 'c': 'Foo'}]
    """)

  def test_call(self):
    self.check("""
      from typing_extensions import Annotated

      class Foo:
          x: Annotated[int, Deprecated("use new api")]
          y: Annotated[int, unit('s', exp=9)]
    """, """
      from typing_extensions import Annotated

      class Foo:
          x: Annotated[int, {'tag': 'Deprecated', 'reason': 'use new api'}]
          y: Annotated[int, {'tag': 'call', 'fn': 'unit', 'posargs': ('s',), 'kwargs': {'exp': 9}}]
    """)


class ErrorTest(test_base.UnitTest):
  """Test parser errors."""

  def test_filename(self):
    src = textwrap.dedent("""
      a: int
      a: int
    """)
    with self.assertRaisesRegex(parser.ParseError, "File.*foo.pyi"):
      parser.parse_pyi(src, "foo.pyi", "foo")

  def test_lineno(self):
    src = textwrap.dedent("""
      class A:
        __slots__ = 0
    """)
    with self.assertRaisesRegex(parser.ParseError, "line 3"):
      parser.parse_pyi(src, "foo.py", "foo")


class ParamsTest(test_base.UnitTest):
  """Test input parameter handling."""

  def test_feature_version(self):
    cases = [
        [(3,), sys.version_info.minor],
        [(3, 7), 7],
        [(3, 8, 2), 8]
    ]
    for version, expected in cases:
      actual = parser._feature_version(version)
      self.assertEqual(actual, expected)


class ParamSpecTest(parser_test_base.ParserTestBase):

  def test_from_typing(self):
    self.check("""
      from typing import Awaitable, Callable, ParamSpec, TypeVar

      P = ParamSpec('P')
      R = TypeVar('R')

      def f(x: Callable[P, R]) -> Callable[P, Awaitable[R]]: ...
    """, """
      from typing import Awaitable, Callable, TypeVar

      R = TypeVar('R')

      def f(x: Callable[..., R]) -> Callable[..., Awaitable[R]]: ...
    """)

  def test_from_typing_extensions(self):
    self.check("""
      from typing import Awaitable, Callable, TypeVar
      from typing_extensions import ParamSpec

      P = ParamSpec('P')
      R = TypeVar('R')

      def f(x: Callable[P, R]) -> Callable[P, Awaitable[R]]: ...
    """, """
      from typing import Awaitable, Callable, TypeVar
      from typing_extensions import ParamSpec

      R = TypeVar('R')

      def f(x: Callable[..., R]) -> Callable[..., Awaitable[R]]: ...
    """)

  def test_custom_generic(self):
    self.check("""
      from typing import Callable, Generic, ParamSpec, TypeVar

      P = ParamSpec('P')
      T = TypeVar('T')

      class X(Generic[T, P]):
          f: Callable[P, int]
          x: T
    """, """
      from typing import Callable, Generic, TypeVar

      P = TypeVar('P')
      T = TypeVar('T')

      class X(Generic[T, P]):
          f: Callable[..., int]
          x: T
    """)

  def test_use_custom_generic(self):
    self.check("""
      from typing import Callable, Generic, TypeVar
      from typing_extensions import ParamSpec

      _T = TypeVar('_T')
      _P = ParamSpec('_P')

      class Foo(Generic[_P, _T]): ...

      def f(x: Callable[_P, _T]) -> Foo[_P, _T]: ...
    """, """
      from typing import Any, Callable, Generic, TypeVar
      from typing_extensions import ParamSpec

      _P = TypeVar('_P')
      _T = TypeVar('_T')

      class Foo(Generic[_P, _T]): ...

      def f(x: Callable[..., _T]) -> Foo[Any, _T]: ...
    """)

  @test_base.skip("ParamSpec in custom generic classes not supported yet")
  def test_double_brackets(self):
    # Double brackets can be omitted when instantiating a class parameterized
    # with only a single ParamSpec.
    self.check("""
      from typing import Generic, ParamSpec

      P = ParamSpec('P')

      class X(Generic[P]): ...

      def f1(x: X[int, str]) -> None: ...
      def f2(x: X[[int, str]]) -> None: ...
    """, """
      from typing import Generic, ParamSpec

      P = ParamSpec('P')

      class X(Generic[P]): ...

      def f1(x: X[int, str]) -> None: ...
      def f2(x: X[int, str]) -> None: ...
    """)

  def test_paramspec_args(self):
    self.check("""
      from typing import Callable, ParamSpec, TypeVar
      P = ParamSpec('P')
      T = TypeVar('T')
      def f(x: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...
    """, """
      from typing import Callable, TypeVar

      T = TypeVar('T')

      def f(x: Callable[..., T], *args, **kwargs) -> T: ...
    """)

  def test_paramspec_args_error(self):
    self.check_error("""
      from typing import Any, Callable
      from typing_extensions import ParamSpec
      _P = ParamSpec("_P")

      class Foo:
        def __init__(
            self, func: Callable[_P, Any], args: _P.args, kwds: _P.kwds
        ) -> None: ...
    """, 7, "Unrecognized ParamSpec attribute: kwds")

  def test_two_classes(self):
    self.check("""
      from typing import Generic, ParamSpec
      P = ParamSpec('P')
      class C1(Generic[P]): ...
      class C2(Generic[P]): ...
    """, """
      from typing import Generic, TypeVar

      P = TypeVar('P')

      class C1(Generic[P]): ...

      class C2(Generic[P]): ...
    """)


class ConcatenateTest(parser_test_base.ParserTestBase):

  def test_from_typing(self):
    self.check("""
      from typing import Callable, Concatenate, ParamSpec, TypeVar

      P = ParamSpec('P')
      R = TypeVar('R')

      class X: ...

      def f(x: Callable[Concatenate[X, P], R]) -> Callable[P, R]: ...
    """, """
      from typing import Callable, TypeVar

      R = TypeVar('R')

      class X: ...

      def f(x: Callable[..., R]) -> Callable[..., R]: ...
    """)

  def test_from_typing_extensions(self):
    self.check("""
      from typing import Callable, TypeVar
      from typing_extensions import Concatenate, ParamSpec

      P = ParamSpec('P')
      R = TypeVar('R')

      class X: ...

      def f(x: Callable[Concatenate[X, P], R]) -> Callable[P, R]: ...
    """, """
      from typing import Callable, TypeVar
      from typing_extensions import Concatenate
      from typing_extensions import ParamSpec

      R = TypeVar('R')

      class X: ...

      def f(x: Callable[..., R]) -> Callable[..., R]: ...
    """)


class UnionOrTest(parser_test_base.ParserTestBase):

  def test_basic(self):
    self.check("""
      def f(x: int | str) -> None: ...
      def g(x: bool | str | float) -> None: ...
      def h(x: str | None) -> None: ...
    """, """
      from typing import Optional, Union

      def f(x: Union[int, str]) -> None: ...
      def g(x: Union[bool, str, float]) -> None: ...
      def h(x: Optional[str]) -> None: ...
    """)


class TypeGuardTest(parser_test_base.ParserTestBase):

  def test_typing_extensions(self):
    self.check("""
      from typing import List
      from typing_extensions import TypeGuard

      def f(x: List[object]) -> TypeGuard[List[str]]: ...
    """, """
      from typing import List
      from typing_extensions import TypeGuard

      def f(x: List[object]) -> bool: ...
  """)

  def test_typing(self):
    self.check("""
      from typing import List, TypeGuard

      def f(x: List[object]) -> TypeGuard[List[str]]: ...
    """, """
      from typing import List

      def f(x: List[object]) -> bool: ...
    """)


class AllTest(parser_test_base.ParserTestBase):

  def check(self, src, expected):
    tree = self.parse(src)
    all_ = [x for x in tree.constants if x.name == "__all__"]
    pyval = all_[0].value if all_ else None
    self.assertEqual(pyval, expected)

  def test_basic(self):
    self.check("""
      __all__ = ["f", "g"]
    """, ("f", "g"))

  def test_tuple(self):
    self.check("""
    __all__ = ("f", "g")
    """, ("f", "g"))

  def test_augment(self):
    self.check("""
      __all__ = ["f", "g"]
      __all__ += ["h"]
    """, ("f", "g", "h"))

  def test_if(self):
    self.check("""
      __all__ = ["f", "g"]
      if sys.version_info > (3, 6, 0):
        __all__ += ["h"]
    """, ("f", "g", "h"))

  def test_else(self):
    self.check("""
      __all__ = ["f", "g"]
      if sys.version_info < (3, 6, 0):
        __all__ += ["e"]
      else:
        __all__ += ["h"]
    """, ("f", "g", "h"))


if __name__ == "__main__":
  unittest.main()
