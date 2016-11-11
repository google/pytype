# -*- coding:utf-8; python-indent:2; indent-tabs-mode:nil -*-
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import textwrap
from pytype.pytd import pytd
from pytype.pytd.parse import decorate
from pytype.pytd.parse import parser
from pytype.pytd.parse import parser_test_base
import unittest


class TestASTGeneration(parser_test_base.ParserTest):

  def TestThrowsSyntaxError(self, src):
    self.assertRaises(parser.ParseError, self.parser.Parse, src)

  def TestRoundTrip(self, src, canonical_src=None, check_the_sourcecode=True):
    """Compile a string, and convert the result back to a string. Compare."""
    if canonical_src is None:
      canonical_src = src
    tree = self.Parse(src)
    new_src = pytd.Print(tree)
    self.AssertSourceEquals(new_src, canonical_src)
    if check_the_sourcecode:
      self.assertMultiLineEqual(canonical_src.rstrip().lstrip("\n"),
                                new_src.rstrip().lstrip("\n"))

  def testImport(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        import abc
        import abc.efg
        from abc import a, b, c
        from abc import (x, y, z,)
        from abc.efg import e, f, g
        from abc import a as aa, b as bb, j
        from abc.efg import d as dd, e as ee, h
        from abc import *
        from abc.efg import *
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        from abc import a
        from abc import b
        from abc import c
        from abc import x
        from abc import y
        from abc import z
        from abc.efg import e
        from abc.efg import f
        from abc.efg import g
        from abc import a as aa
        from abc import b as bb
        from abc import j
        from abc.efg import d as dd
        from abc.efg import e as ee
        from abc.efg import h
    """))

  def testAliasForImport(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        import abc
        X = abc.X
        Y = abc.Y
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        from abc import X
        from abc import Y
        """))

  def testImportErrors(self):
    """Test import errors."""
    self.TestThrowsSyntaxError(textwrap.dedent("""
        import abc as efg
    """))
    self.TestThrowsSyntaxError(textwrap.dedent("""
        import abc.efg as efg
    """))

  def testImportTyping(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        import typing
        def f(x: typing.List[int]) -> typing.Tuple[int, ...]: ...
        """)
    # TODO(kramm): Should List and Tuple be fully qualified?
    self.TestRoundTrip(src, textwrap.dedent("""
        from typing import List, Tuple

        def f(x: List[int]) -> Tuple[int, ...]: ...
        """))

  def testParenthesisImport(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        from abc import (
            a, b, c, d,
            e, f, g, h)
        x = ...  # type: a
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        import abc

        from abc import a
        from abc import b
        from abc import c
        from abc import d
        from abc import e
        from abc import f
        from abc import g
        from abc import h

        x = ...  # type: abc.a
    """))

  def testImportAs(self):
    """Test parsing of 'import as'."""
    src = textwrap.dedent("""
        from typing import Tuple as TypingTuple
        _attributes = ...  # type: TypingTuple[str, ...]
    """)
    self.TestRoundTrip(src, textwrap.dedent("""
        from typing import Tuple

        _attributes = ...  # type: Tuple[str, ...]
        """))

  def testRenaming(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        from foobar import SomeClass

        class A(SomeClass): ...
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        import foobar

        from foobar import SomeClass

        class A(foobar.SomeClass):
            pass
    """))

  def testRenaming2(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        from foo.bar import Base as BaseClass

        class A(BaseClass): ...
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        import foo.bar

        from foo.bar import Base as BaseClass

        class A(foo.bar.Base):
            pass
    """))

  def testDocStrings(self):
    """Test doc strings."""
    src = textwrap.dedent("""
        \"\"\"Lorem ipsum\"\"\"
        """)
    self.TestRoundTrip(src, "")  # Doc strings are ignored

  def testMultiLineDocStrings(self):
    """Test doc strings over multiple lines."""
    src = textwrap.dedent("""
        \"\"\"Lorem ipsum
        dolor sit "amet", consectetur adipiscing elit, sed do eiusmod
        tempor incididunt ut labore et dolore magna aliqua. Ut enim
        \"\"\"
        """)
    self.TestRoundTrip(src, "")  # Doc strings are ignored

  def testClassDocStrings(self):
    """Test doc strings in classes."""
    src = textwrap.dedent("""
        class A(object):
          \"\"\"Implements the "A" functionality.\"\"\"

        class B(object):
          \"\"\"Implements the "B" functionality.\"\"\"
          pass

        class C(object):
          \"\"\"Implements the "C" functionality.

          \"\"\"
          ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testFunctionDocStrings(self):
    """Test doc strings in functions."""
    src = textwrap.dedent("""
        def random() -> int:
          \"\"\"Returns a random integer.\"\"\"
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOneFunction(self):
    """Test parsing of a single function definition."""
    # a function def with two params
    src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int raises Foo, Test: ...
        """)
    self.TestRoundTrip(src)

  def testBackticks(self):
    """Test parsing of names in backticks."""
    src = textwrap.dedent("""
      def `foo-bar`(x: `~unknown3`) -> `funny-type`[int]: ...
      """)
    self.TestRoundTrip(src)

  def testOneDottedFunction(self):
    """Test parsing of a single function with dotted names."""
    # We won't normally use __builtins__ ... this is just for testing.
    src = textwrap.dedent("""
        def foo(a: __builtins__.int) -> __builtins__.int raises foo.Foo: ...
        def qqsv(x_or_y: compiler.symbols.types.BooleanType) -> None: ...
        """)
    expected = (textwrap.dedent("""
        import __builtins__
        import compiler.symbols.types
        import foo
        """) + src)
    self.TestRoundTrip(src, expected)

  def testEllipsis1(self):
    """Test parsing of function bodies."""
    src = textwrap.dedent("""
        def f(x) -> None: ...
        def f(x) -> None:
          ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testMissingReturn(self):
    """Test parsing of functions without a return type."""
    src = textwrap.dedent("""
        def f(x): ...
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        from typing import Any

        def f(x) -> Any: ...
        """))

  def testEllipsis2(self):
    """Test parsing of class bodies."""
    src = textwrap.dedent("""
        class A(object):
          ...
        class B(object): ...
        class C(object):
          pass
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testAny(self):
    """Test parsing of 'Any'."""
    src = textwrap.dedent("""
        def eval(s: str) -> Any: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testQuotes(self):
    """Test parsing of quoted types."""
    src = textwrap.dedent("""
        def occurences() -> "Dict[str, List[int]]": ...
        class A(object): ...
        def invert(d: 'Dict[A, A]') -> 'Dict[A, A]': ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testCallable(self):
    """Test parsing Callable."""
    src = textwrap.dedent("""
        def get_listener() -> Callable[[int, int], str]": ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testAlias(self):
    """Test parsing Callable."""
    src = textwrap.dedent("""
        StrDict = Dict[str, str]
        def get_listener(x: StrDict) -> StrDict: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testDefineTrueFalse(self):
    """Test defining True/False."""
    src = textwrap.dedent("""
        True = ...  # type: bool
        False = ...  # type: bool
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testDecorator(self):
    """Test overload decorators."""
    src = textwrap.dedent("""
        @overload
        def abs(x: int) -> int: ...
        @overload
        def abs(x: float) -> float: ...

        class A(object):
          @overload
          def abs(self, x: int, y: int) -> int: ...
          @overload
          def abs(self, x: float, y: float) -> float: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOtherDecorators(self):
    """Test overload decorators."""
    src = textwrap.dedent("""
        class A(object):
            @staticmethod
            def name() -> str: ...
            @classmethod
            def version(cls) -> int: ...
        """)
    self.TestRoundTrip(src)

  def testPropertyDecorator(self):
    """Test property decorators."""
    expected = textwrap.dedent("""
        class A(object):
            name = ...  # type: str
      """)

    def MatchExpected(src):
      self.TestRoundTrip(textwrap.dedent(src), expected)

    MatchExpected("""
        class A(object):
            @property
            def name(self) -> str:...
            """)

    MatchExpected("""
        class A(object):
            @name.setter
            def name(self, value: str) -> None: ...
            """)

    MatchExpected("""
        class A(object):
            @property
            def name(self) -> str:...

            @name.setter
            def name(self, value: str) -> None: ...
            """)

    MatchExpected("""
        class A(object):
            @property
            def name(self) -> str:...

            @name.setter
            def name(self, value) -> None: ...
            """)

    MatchExpected("""
        class A(object):
            @property
            def name(self) -> int:...

            # Last type gets used (should improve).
            @name.setter
            def name(self, value: str) -> None: ...
            """)

  def testPropertyDecoratorAnyType(self):
    """Test property decorators that don't provide a type."""
    expected = textwrap.dedent("""
          from typing import Any

          class A(object):
              name = ...  # type: Any
              """)

    def MatchExpected(src):
      self.TestRoundTrip(textwrap.dedent(src), expected)

    MatchExpected("""
        class A(object):
            @property
            def name(self): ...
            """)

    MatchExpected("""
        class A(object):
            @name.setter
            def name(self, value): ...
            """)

    MatchExpected("""
        class A(object):
            @name.deleter
            def name(self): ...
            """)

  def testPropertyDecoratorBadSyntax(self):
    """Property decorator uses that should give errors."""
    def ExpectError(src):
      self.TestThrowsSyntaxError(textwrap.dedent(src))

    ExpectError("""
        class A(object):
            @property
            def name(self, bad_arg): ...
            """)

    ExpectError("""
        class A(object):
            @name.setter
            def name(self): ...
            """)

    ExpectError("""
        class A(object):
            @name.foo
            def name(self): ...
            """)

    ExpectError("""
        class A(object):
            @notname.deleter
            def name(self): ...
            """)

    ExpectError("""
        class A(object):
            @property
            @staticmethod
            def name(self): ...
            """)

    ExpectError("""
        class A(object):
            @property
            def name(self): ...

            def name(self): ...
            """)

    ExpectError("""
        @property
        def name(self): ...
        """)

  def testRaise(self):
    """Test raise statements."""
    src = textwrap.dedent("""
        def read(x) -> None:
            raise IndexError
            raise IOError()
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testHomogeneous(self):
    src = textwrap.dedent("""
        def f() -> Tuple[int, ...]: ...
    """)
    expected = "from typing import Tuple\n" + src
    self.TestRoundTrip(src, expected)

  def testTuple(self):
    src = textwrap.dedent("""
        def walk() -> Tuple[AnyStr, List[AnyStr]]
    """)
    self.TestRoundTrip(src, textwrap.dedent("""
        import typing
        from typing import List, Tuple, Union

        def walk() -> Tuple[Union[typing.AnyStr, List[typing.AnyStr]], ...]: ...
    """))

  def testGeneric(self):
    src = textwrap.dedent("""
        X = TypeVar('X')
        Y = TypeVar('Y')

        class T1(typing.Generic[X], object):
            pass

        class T2(typing.Generic[X, Y], T1):
            pass

        class T3(typing.Generic[X, Y], T1, T2):
            pass
    """)
    expected = (textwrap.dedent("""
        import typing
        from typing import TypeVar
    """) + src)
    self.TestRoundTrip(src, expected)

  def testGenericIgnoreExtraArgs(self):
    src1 = textwrap.dedent("""
        import typing
        from typing import TypeVar

        X = TypeVar('X', covariant=True)

        class T1(typing.Generic[X], object):
            pass
    """)

    src2 = textwrap.dedent("""
        import typing
        from typing import TypeVar

        X = TypeVar('X')

        class T1(typing.Generic[X], object):
            pass
    """)

    self.TestRoundTrip(src1, src2)

  def testGenericRequiresArg(self):
    """Test TypeVar arg-checking."""
    srcs = [
        "X = TypeVar()",
        "X = TypeVar(0)",
        "X = TypeVar('')",
        "X = TypeVar(,)"]

    for src in srcs:
      self.TestThrowsSyntaxError(src)

  def testTemplated(self):
    src = textwrap.dedent("""
        S = TypeVar('S')
        T = TypeVar('T')
        X = TypeVar('X')
        Y = TypeVar('Y')

        def foo(x: int) -> T1[float]: ...
        def foo(x: int) -> T2[int, complex]: ...
        def foo(x: int) -> T3[int, T4[str]]: ...
        def bar(y: int) -> T1[float]: ...
        def qqsv(x: T) -> List[T]: ...
        def qux(x: T) -> List[S]: ...

        class T1(typing.Generic[X], object):
            def foo(a: X) -> T2[X, int] raises float: ...

        class T2(typing.Generic[X, Y], object):
            def foo(a: X) -> complex raises Except[X, Y]: ...
    """)
    expected = (textwrap.dedent("""
        import typing
        from typing import List, TypeVar
    """) + src)
    self.TestRoundTrip(src, expected)

  def testOptionalParameters(self):
    """Test parsing of individual optional parameters."""
    src = textwrap.dedent("""
        def f(x) -> int: ...
        def f(x = ...) -> int: ...
        def f(x: int = ...) -> int: ...
        def f(x, s: str = ..., t: str = ...) -> int: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOptionalParametersWithType(self):
    """Test parsing of individual optional parameters."""
    src = textwrap.dedent("""
        def f(x = 0) -> int: ...
        def f(x: int = None) -> int: ...
        def f(x, s: str = None) -> int: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOnlyOptional(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(...) -> int: ...
    """).strip()
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOptional1(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(a: int, ...) -> int: ...
    """).strip()
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOptional2(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(a: int, c: bool, ...) -> int: ...
    """).strip()
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOptional3(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(a: int, c: bool, *args, **kwargs) -> int: ...
    """).strip()
    self.TestRoundTrip(src)

  def testOptional4(self):
    """Test parsing Callable."""
    src = textwrap.dedent("""
        def f(args, kwargs, *x, **y) -> int: ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testBareStar1(self):
    """Test parsing of keyword-only syntax."""
    src = textwrap.dedent("""
        def f(x, *, y = ...) -> None: ...
        def g(*, y = ...) -> None: ...
        """)
    self.TestRoundTrip(src)

  def testBareStar(self):
    """Test keyword-only syntax errors."""
    self.TestThrowsSyntaxError("def f(*): ...")
    self.TestThrowsSyntaxError("def f(*,): ...")
    self.TestThrowsSyntaxError("def f(*args, *, b=1): ...")
    self.TestThrowsSyntaxError("def f(**kwargs, *, b=1): ...")

  def testKwArgs(self):
    """Test parsing of *args, **kwargs."""
    src = textwrap.dedent("""
        def f(x, *args) -> None: ...
        def g(x, *args, **kwargs) -> None: ...
        def h(x, **kwargs) -> None: ...
        """)
    self.TestRoundTrip(src)

  def testTypedKwArgs(self):
    """Test parsing of *args, **kwargs with types."""
    src = textwrap.dedent("""
        def f(x, *args: int) -> None: ...
        def g(x, *args: int or str, **kwargs: str) -> None: ...
        def h(x, **kwargs: Optional[int]) -> None: ...
        """)
    self.TestRoundTrip(src, src, check_the_sourcecode=False)

  def testConstants(self):
    """Test parsing of constants."""
    src = textwrap.dedent("""
      a = ...  # type: int
      b = ...  # type: Union[int, float]
    """).strip()
    expected = "from typing import Union\n\n" + src
    self.TestRoundTrip(src, expected)

  def testBoolConstant(self):
    """Test abbreviated constant definitions."""
    src = textwrap.dedent("""
        a = 0
        b = True
        c = False
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
        a = ...  # type: int
        b = ...  # type: bool
        c = ...  # type: bool
    """))

  def testUnion(self):
    """Test parsing of Unions."""
    src = textwrap.dedent("""
        a = ...  # type: Union[int, float]
        b = ...  # type: int or float or complex
        c = ...  # type: typing.Union[int, float, complex]
    """)
    expected = textwrap.dedent("""
        from typing import Union

        a = ...  # type: Union[int, float]
        b = ...  # type: Union[int, float, complex]
        c = ...  # type: Union[int, float, complex]
    """)
    self.TestRoundTrip(src, expected)

  def testAnythingType(self):
    """Test parsing of Any."""
    src = textwrap.dedent("""
        a = ...  # type: ?
        b = ...  # type: Any
        c = ...  # type: typing.Any
    """)
    self.TestRoundTrip(src, textwrap.dedent("""
        from typing import Any

        a = ...  # type: Any
        b = ...  # type: Any
        c = ...  # type: Any
    """))

  def testReturnTypes(self):
    src = textwrap.dedent("""
        def a() -> Any: ...
        def b() -> Any: ...
        def c() -> object: ...
        def d() -> None: ...
        def e() -> a or b: ...
        def f() -> a[x, ...]: ...
        def g() -> a[x]: ...
        def h() -> a[x, y]: ...
        def i() -> nothing: ...  # never returns
    """)
    result = self.Parse(src)
    ret = {f.name: f.signatures[0].return_type for f in result.functions}
    self.assertIsInstance(ret["a"], pytd.AnythingType)
    self.assertIsInstance(ret["b"], pytd.AnythingType)
    self.assertEquals(ret["c"], pytd.NamedType("object"))
    self.assertEquals(ret["d"], pytd.NamedType("NoneType"))
    self.assertIsInstance(ret["e"], pytd.UnionType)
    self.assertIsInstance(ret["f"], pytd.HomogeneousContainerType)
    self.assertIsInstance(ret["g"], pytd.GenericType)
    self.assertIsInstance(ret["h"], pytd.GenericType)
    self.assertIsInstance(ret["i"], pytd.NothingType)

  def testTemplateReturn(self):
    src = textwrap.dedent("""
        def foo(a: Union[int, float], c: bool) -> List[int] raises Foo, Test: ...
    """)
    expected = textwrap.dedent("""
        from typing import List

        def foo(a: float, c: bool) -> List[int] raises Foo, Test: ...
    """)
    self.TestRoundTrip(src, expected)

  def testPass(self):
    src = textwrap.dedent("""
        class Foo(Bar):
            pass
    """)
    self.TestRoundTrip(src)

  def testIndent(self):
    src = textwrap.dedent("""
        class Foo(object):
          def bar() -> ?
        def baz(i: int) -> Any: ...
    """)
    result = self.Parse(src)
    foo = result.Lookup("Foo")
    self.assertEquals(["bar"], [f.name for f in foo.methods])
    self.assertEquals(["baz"], [f.name for f in result.functions])

  def testFunctionTypeParams(self):
    src = textwrap.dedent("""
        T1 = TypeVar('T1')

        def f(x: T1) -> T1: ...
    """)
    expected = "from typing import TypeVar\n" + src
    self.TestRoundTrip(src, expected)

  def testSpaces(self):
    """Test that start-of-file / end-of-file whitespace is handled correctly."""
    self.TestRoundTrip("def f() -> int", check_the_sourcecode=False)
    self.TestRoundTrip("def f() -> int\n", check_the_sourcecode=False)
    self.TestRoundTrip("\ndef f() -> int", check_the_sourcecode=False)
    self.TestRoundTrip("\ndef f() -> int", check_the_sourcecode=False)
    self.TestRoundTrip("\n\ndef f() -> int", check_the_sourcecode=False)
    self.TestRoundTrip("  \ndef f() -> int", check_the_sourcecode=False)
    self.TestRoundTrip("def f() -> int  ", check_the_sourcecode=False)
    self.TestRoundTrip("def f() -> int  \n", check_the_sourcecode=False)
    self.TestRoundTrip("def f() -> int\n  ", check_the_sourcecode=False)
    self.TestRoundTrip("def f() -> int\n\n", check_the_sourcecode=False)

  def testSpacesWithIndent(self):
    self.TestRoundTrip("def f(x: list[nothing]) -> ?:\n    x := list[int]",
                       check_the_sourcecode=False)
    self.TestRoundTrip("\ndef f(x: list[nothing]) -> ?:\n    x := list[int]",
                       check_the_sourcecode=False)
    self.TestRoundTrip("\ndef f(x: list[nothing]) -> ?:\n    x := list[int]  ",
                       check_the_sourcecode=False)
    self.TestRoundTrip("def f(x: list[nothing]) -> ?:\n    x := list[int]  \n",
                       check_the_sourcecode=False)
    self.TestRoundTrip("def f(x: list[nothing]) -> ?:\n    x := list[int]\n  ",
                       check_the_sourcecode=False)

  def testAlignedComments(self):
    src = textwrap.dedent("""
        # comment 0
        class Foo(object): # eol line comment 0
          # comment 1
          def bar(x: list[nothing]) -> ?: # eol line comment 1
            # comment 2
            x := list[float] # eol line comment 2
            # comment 3
          # comment 4
        # comment 5
        def baz(i: list[nothing]) -> ?: # eol line comment 3
          # comment 6
          i := list[int] # eol line comment 4
          # comment 7
        # comment 8
    """)
    dest = textwrap.dedent("""
        def baz(i: list[nothing]) -> ?:
            i := list[int]

        class Foo(object):
            def bar(x: list[nothing]) -> ?:
                x := list[float]
    """)
    self.TestRoundTrip(src, dest, check_the_sourcecode=False)

  def testUnalignedComments(self):
    src = textwrap.dedent("""
          # comment 0
        class Foo(object):
            # comment 1
          def bar(x: X) -> ?:
              # comment 2
            x := X # eol line comment 2
               # comment 3
         # comment 4
          c = ...  # type: int
        def baz(i: X) -> ?:
           # comment 6
          i := X
            # comment 6
    """)
    dest = textwrap.dedent("""
        from typing import Any

        def baz(i: X) -> Any:
            i := X

        class Foo(object):
            c = ...  # type: int
            def bar(x: X) -> Any:
                x := X
    """)
    self.TestRoundTrip(src, dest)

  def testDuplicates4(self):
    src = textwrap.dedent("""
        class A(object):
          pass
        class A(object):
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates5(self):
    src = textwrap.dedent("""
        def x()
        class x(object):
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates6(self):
    src = textwrap.dedent("""
        x = ...  # type: int
        class x(object):
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates7(self):
    src = textwrap.dedent("""
        x = ...  # type: int
        def x(): ...
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates8(self):
    src = textwrap.dedent("""
       def bar(x: int) -> NoneType: ...
       def foo PYTHONCODE
       def bar(x: float) -> str: ...
       def foo PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates8b(self):
    src = textwrap.dedent("""
    class Foo(object):
       def bar(x: int) -> NoneType: ...
       def foo PYTHONCODE
       def bar(x: float) -> str: ...
       def foo PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates9(self):
    src = textwrap.dedent("""
       def bar(x: int) -> NoneType: ...
       def bar PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates9b(self):
    src = textwrap.dedent("""
    class Foo(object):
       def bar(x: int) -> NoneType: ...
       def bar PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates10(self):
    src = textwrap.dedent("""
        # foobar
        class A(object):
          pass
        class A(object):
          pass
    """)
    try:
      self.parser.Parse(src)
    except parser.ParseError as e:
      self.assertNotIn("foobar", str(e))
      self.assertNotIn("^", str(e))
    else:
      self.fail("Should have raised error")

  def testPythonCode1(self):
    """Smoke test for PYTHONCODE."""
    src = textwrap.dedent("""
      def bar PYTHONCODE
    """)
    self.TestRoundTrip(src)

  def testPythonCode2(self):
    """Smoke test for PYTHONCODE."""
    src = textwrap.dedent("""
    class Foo(object):
        def bar PYTHONCODE
    """)
    self.TestRoundTrip(src)

  def testMutable(self):
    src = textwrap.dedent("""
        class Foo(object):
          def append_int(l: list) -> ?:
            l := List[int]
        def append_float(l: list) -> ?:
          l := List[float]
    """)
    module = self.Parse(src)
    foo = module.Lookup("Foo")
    self.assertEquals(["append_int"], [f.name for f in foo.methods])
    self.assertEquals(["append_float"], [f.name for f in module.functions])
    append_int = foo.methods[0].signatures[0]
    append_float = module.functions[0].signatures[0]
    self.assertIsNotNone(append_int.params[0].mutated_type)
    self.assertIsNotNone(append_float.params[0].mutated_type)

  def testMutableOptional(self):
    src = textwrap.dedent("""
        def append_float(l: list = ...) -> int:
          l := list[float]
    """)
    self.TestThrowsSyntaxError(src)

  def testMutableRoundTrip(self):
    src = textwrap.dedent("""
        def append_float(l: list) -> Any:
            l := List[float]

        class Foo(object):
            def append_int(l: list) -> Any:
                l := List[int]
    """)
    expected = "from typing import Any, List\n" + src
    self.TestRoundTrip(src, expected)

  def testDottedNames(self):
    """Test parsing of names with dots."""
    src = textwrap.dedent("""
      a = ... # type: Foo
      b = ... # type: x.Bar
      c = ... # type: x.y.Baz
      """)
    result = self.Parse(src)
    self.assertEquals(pytd.NamedType("Foo"), result.Lookup("a").type)
    self.assertEquals(pytd.NamedType("x.Bar"), result.Lookup("b").type)
    self.assertEquals(pytd.NamedType("x.y.Baz"), result.Lookup("c").type)

  def testMultiFunction(self):
    """Test parsing of multiple function defs including overloaded version."""

    data = textwrap.dedent("""
        # several function defs with different sigs
        def foo(a : int, c : bool) -> int raises Test, Foo: ...
        def foo() -> None: ...
        def add(x : int, y : int) -> int: ...
        """)

    result = self.Parse(data)

    f = result.Lookup("add")
    self.assertEquals(len(f.signatures), 1)
    self.assertEquals(["int", "int"],
                      [p.type.name
                       for p in f.signatures[0].params])

    f = result.Lookup("foo")
    self.assertEquals(len(f.signatures), 2)

    sig1, = [s for s in f.signatures if not s.params]
    self.assertEquals(sig1.return_type.name, "NoneType")
    sig2, = [s for s in f.signatures if len(s.params) == 2]
    self.assertEquals(sig2.return_type.name, "int")
    self.assertEquals([p.type.name for p in sig2.params],
                      ["int", "bool"])

  def testComplexFunction(self):
    """Test parsing of a function with unions, none-able etc."""

    canonical = textwrap.dedent("""
        def foo(a: int, b: float or None, c: Foo or `s`.`Bar` or Zot) -> int raises Bad
    """)
    data1 = textwrap.dedent("""
        def foo(a: int, b: int or float or None, c: Foo or s.Bar or Zot) -> int raises Bad
    """)
    data2 = textwrap.dedent("""
        def foo(a: int, b: int or (float or None), c: Foo or (s.Bar or Zot)) -> int raises Bad
    """)
    data3 = textwrap.dedent("""
        def foo(a: int, b: (int or float) or None, c: (Foo or s.Bar) or Zot) -> int raises Bad
    """)
    data4 = textwrap.dedent("""
        def foo(a: int, b: ((((int or float)) or ((None)))), c: (((Foo) or s.Bar or (Zot)))) -> int raises Bad
    """)

    self.TestRoundTrip(data1, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data2, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data3, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data4, canonical, check_the_sourcecode=False)

  def testNoReturnType(self):
    """Test a parsing error (no return type)."""

    data1 = "def foo() -> Any: ..."
    data2 = "def foo() -> None: ..."

    self.TestRoundTrip(data1,
                       "from typing import Any\n\n" + data1)
    self.TestRoundTrip(data2)

  def testVersionSplitFunction(self):
    """Test version conditionals."""
    data = textwrap.dedent("""
    if sys.version_info < (3,):
      c1 = ...  # type: int
      def f() -> ?
      class A(object):
        pass
    else:
      c2 = ...  # type: int
      def g() -> ?
      class B(object):
        pass

    class Foo(object):
      if sys.version_info > (2, 7, 3):
        attr2 = ...  # type: int
        def m2() -> ?
      else:
        attr1 = ...  # type: int
        def m1() -> ?
    """)
    unit = self.Parse(data, version=(2, 7, 3))
    self.assertEquals([f.name for f in unit.functions], ["f"])
    self.assertEquals([f.name for f in unit.classes], ["A", "Foo"])
    self.assertEquals([f.name for f in unit.constants], ["c1"])
    self.assertEquals([f.name for f in unit.Lookup("Foo").methods], ["m1"])
    self.assertEquals([f.name for f in unit.Lookup("Foo").constants], ["attr1"])
    unit = self.Parse(data, version=(3, 3))
    self.assertEquals([f.name for f in unit.functions], ["g"])
    self.assertEquals([f.name for f in unit.classes], ["B", "Foo"])
    self.assertEquals([f.name for f in unit.constants], ["c2"])
    self.assertEquals([f.name for f in unit.Lookup("Foo").methods], ["m2"])
    self.assertEquals([f.name for f in unit.Lookup("Foo").constants], ["attr2"])

  def testVersionSyntax(self):
    data = textwrap.dedent("""
    if sys.version_info < (3,):
      c1 = ...  # type: int
    if sys.version_info < (3, 1):
      c2 = ...  # type: int
    if sys.version_info < (3, 1, 1):
      c3 = ...  # type: int
    if sys.version_info <= (3,):
      c4 = ...  # type: int
    if sys.version_info <= (3, 1):
      c5 = ...  # type: int
    if sys.version_info <= (3, 1, 1):
      c6 = ...  # type: int
    if sys.version_info > (3,):
      c7 = ...  # type: int
    if sys.version_info > (3, 1):
      c8 = ...  # type: int
    if sys.version_info > (3, 1, 1):
      c9 = ...  # type: int
    if sys.version_info >= (3,):
      c10 = ...  # type: int
    if sys.version_info >= (3,1):
      c11 = ...  # type: int
    if sys.version_info >= (3, 1, 1):
      c12 = ...  # type: int
    if sys.version_info == (3, 0, 0):
      c13 = ...  # type: int
    if sys.version_info != (3, 0, 0):
      c14 = ...  # type: int
    """)
    unit = self.Parse(data, version=(3, 0, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["c2", "c3", "c4", "c5", "c6", "c10", "c13"])
    unit = self.Parse(data, version=(3, 1, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["c3", "c5", "c6", "c7", "c10", "c11", "c14"])
    unit = self.Parse(data, version=(3, 1, 1))
    self.assertEquals([f.name for f in unit.constants],
                      ["c6", "c7", "c8", "c10", "c11", "c12", "c14"])

  def testVersionNormalization(self):
    data = textwrap.dedent("""
    if sys.version_info <= (3,):
      c1 = ...  # type: int
    if sys.version_info <= (3, 0):
      c2 = ...  # type: int
    if sys.version_info <= (3, 0, 0):
      c3 = ...  # type: int
    if sys.version_info > (3,):
      c4 = ...  # type: int
    if sys.version_info > (3, 0):
      c5 = ...  # type: int
    if sys.version_info > (3, 0, 0):
      c6 = ...  # type: int
    """)
    unit = self.Parse(data, version=(3, 0, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["c1", "c2", "c3"])
    unit = self.Parse(data, version=(3, 0, 1))
    self.assertEquals([f.name for f in unit.constants],
                      ["c4", "c5", "c6"])

  def testPlatform(self):
    data = textwrap.dedent("""
      if sys.platform == 'win32':
        c1 = ...  # type: int
      if sys.platform != 'win32':
        c2 = ...  # type: int
      if sys.platform == 'linux':
        c3 = ...  # type: int
      if sys.platform != 'linux':
        c4 = ...  # type: int
      if sys.platform == 'foobar':
        c5 = ...  # type: int
      if sys.platform != 'foobar':
        c6 = ...  # type: int
    """)
    unit = self.Parse(data, platform="linux")
    self.assertEquals([f.name for f in unit.constants],
                      ["c2", "c3", "c6"])
    unit = self.Parse(data, platform="win32")
    self.assertEquals([f.name for f in unit.constants],
                      ["c1", "c4", "c6"])

  def testElif(self):
    data = textwrap.dedent("""
    if sys.version_info < (3,):
      a1 = ...  # type: int
    elif sys.version_info > (3, 5):
      a2 = ...  # type: int

    if sys.version_info < (3,):
      b1 = ...  # type: int
    elif sys.version_info > (3, 5):
      b2 = ...  # type: int
    elif sys.platform == 'win32':
      b3 = ...  # type: int

    if sys.version_info < (3,):
      c1 = ...  # type: int
    elif sys.version_info > (3, 5):
      c2 = ...  # type: int
    else:
      c3 = ...  # type: int

    if sys.version_info < (3,):
      d1 = ...  # type: int
    elif sys.version_info > (3, 5):
      d2 = ...  # type: int
    elif sys.platform == 'win32':
      d3 = ...  # type: int
    else:
      d4 = ...  # type: int
    """)
    unit = self.Parse(data, version=(2, 7, 6))
    self.assertEquals([f.name for f in unit.constants],
                      ["a1", "b1", "c1", "d1"])
    unit = self.Parse(data, version=(3, 6, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["a2", "b2", "c2", "d2"])
    unit = self.Parse(data, version=(3, 3, 3), platform="win32")
    self.assertEquals([f.name for f in unit.constants],
                      ["b3", "c3", "d3"])
    unit = self.Parse(data, version=(3, 3, 3), platform="linux")
    self.assertEquals([f.name for f in unit.constants],
                      ["c3", "d4"])

  def testTemplateSimple(self):
    """Test simple class template."""
    data = textwrap.dedent("""
        T = TypeVar('T')

        class MyClass(typing.Generic[T], object):
            def f(self, T) -> T: ...
        """)
    expected = (textwrap.dedent("""
        import typing
        from typing import TypeVar
        """) + data)
    self.TestRoundTrip(data, expected)

  def testTemplateNameReuseOnClass(self):
    """Test name reuse between templated classes."""
    data = textwrap.dedent("""
        T = TypeVar('T')

        class MyClass1(typing.Generic[T], object):
            def f(self, T) -> T: ...

        class MyClass2(typing.Generic[T], object):
            def f(self, T) -> T: ...
        """)
    expected = (textwrap.dedent("""
        import typing
        from typing import TypeVar
        """) + data)
    self.TestRoundTrip(data, expected)

  def testTemplateNameReuseOnMethods(self):
    """Test name reuse between methods."""
    data = textwrap.dedent("""
        T = TypeVar('T')
        V = TypeVar('V')

        class MyClass1(typing.Generic[T], object):
            def f(self, T, V) -> V: ...

        class MyClass2(typing.Generic[T], object):
            def f(self, T, V) -> V: ...
        """)
    self.TestRoundTrip(data, check_the_sourcecode=False)

  def testScopedTypevar(self):
    """Test type parameters as class attributes (not supported)."""
    data = textwrap.dedent("""
        class MyClass1(object):
            SomeType = TypeVar('SomeType')
            def g(x: SomeType) -> SomeType: ...
    """)
    self.TestThrowsSyntaxError(data)

  def testTypeVarReuseOnGlobalMethods(self):
    """Test two global methods sharing a type variable."""
    data = textwrap.dedent("""
        T = TypeVar('T')

        def f(x: T) -> T: ...
        def g(x: T) -> T: ...
        """)
    self.TestRoundTrip(data, textwrap.dedent("""
        from typing import TypeVar

        T = TypeVar('T')

        def f(x: T) -> T: ...
        def g(x: T) -> T: ...
    """))

  def testTemplates(self):
    """Test template parsing."""

    data = textwrap.dedent("""
        T = TypeVar('T')
        C = TypeVar('C')
        class MyClass(typing.Generic[C], object):
          def f1(p1: C) -> ?
          def f2(p1: C, p2: T, p3: dict[C, C or T or int]) -> T raises Error[T]
        """)

    result = self.Parse(data)
    myclass = result.Lookup("MyClass")
    self.assertEquals({t.name for t in myclass.template}, {"C"})

    f1 = myclass.Lookup("f1").signatures[0]
    param = f1.params[0]
    self.assertEquals(param.name, "p1")
    self.assertIsInstance(param.type, pytd.TypeParameter)

    f2 = myclass.Lookup("f2").signatures[0]
    self.assertEquals([p.name for p in f2.params], ["p1", "p2", "p3"])
    self.assertEquals([t.name for t in f2.template], ["T"])
    p1, p2, p3 = f2.params
    t1, t2, t3 = p1.type, p2.type, p3.type
    self.assertIsInstance(t1, pytd.TypeParameter)
    self.assertIsInstance(t2, pytd.TypeParameter)
    self.assertNotIsInstance(t3, pytd.TypeParameter)
    self.assertEquals(t3.base_type.name, "dict")
    self.assertIsInstance(f2.return_type, pytd.TypeParameter)
    self.assertEquals(f2.return_type.name, "T")
    self.assertEquals(len(f2.exceptions), 1)
    self.assertEquals(len(f2.template), 1)

  def testNestedTemplate(self):
    """Test nested template parsing."""

    data = textwrap.dedent("""
        K = TypeVar('K')
        V = TypeVar('V')
        class MyClass(typing.List[typing.Tuple[K or V]]): ...
        """)

    result = self.Parse(data)
    myclass = result.Lookup("MyClass")
    self.assertEquals({t.name for t in myclass.template}, {"K", "V"})

  def testSelf(self):
    """Test handling of self."""

    data = textwrap.dedent("""
        U = TypeVar('U')
        V = TypeVar('V')
        class MyClass(typing.Generic[U, V], object):
          def f1(self) -> ?: ...
        """)

    result = self.Parse(data)
    myclass = result.Lookup("MyClass")
    self.assertEquals([t.name for t in myclass.template], ["U", "V"])

    f = myclass.Lookup("f1").signatures[0]
    self_param = f.params[0]
    self.assertEquals(self_param.name, "self")
    u, v = myclass.template
    self.assertEquals(self_param.type,
                      pytd.GenericType(pytd.NamedType("MyClass"),
                                       (u.type_param, v.type_param)))

  def testAutoGenerated(self):
    """Test some source that caused a bug."""
    src = textwrap.dedent("""
        def foo(a: List[bool], b: Union[X, Y]) -> Z:
            a := List[int]
        def bar(a: int, b: List[int]) -> Z:
            b := List[complex]
        def bar(a: int, b: List[float]) -> Z:
            b := List[str]""")
    expected = "from typing import List, Union\n" + src
    self.TestRoundTrip(src, expected)

  def testMissingTypeComment(self):
    self.TestRoundTrip(textwrap.dedent("""
      x = ...
    """), textwrap.dedent("""
      from typing import Any

      x = ...  # type: Any
    """))

  def testTypeCommentSpaces(self):
    """Test types in comments."""
    self.TestRoundTrip(textwrap.dedent("""
      x = ...  # type: List[int]
      y = ... # type: int
      z = ...# type: float
    """), textwrap.dedent("""
      from typing import List

      x = ...  # type: List[int]
      y = ...  # type: int
      z = ...  # type: float
    """))

  def testNamedTupleParse(self):
    """Test NamedTuple parsing variations."""

    data = textwrap.dedent("""
        from typing import NamedTuple

        class C1(NamedTuple("nt", [])):
          pass

        class C2(NamedTuple("nt", [("f1", int), ("f2", int)])):
          pass

        class C3(NamedTuple("nt", [("f1", int,), ])):
          pass

        class C4(NamedTuple("nt", [("f1", NamedTuple("nt", []))])):
          pass
        """)

    self.Parse(data)

  def testNamedTupleDedup(self):
    """Test NamedTuple class dedup."""

    src = textwrap.dedent("""
        from typing import NamedTuple, Tuple

        x = ... # type: NamedTuple("nt", [("f1", int), ("f2", float)])
        y = ... # type: NamedTuple("nt", [("f1", int)])
        """)

    tree = self.Parse(src)
    x = tree.Lookup("x")
    y = tree.Lookup("y")
    self.assertNotEqual(x.type, y.type)
    self.assertNotEqual(tree.Lookup(x.type.name), tree.Lookup(y.type.name))

  def testNamedTupleMatchesTuple(self):
    """Test that NamedTuple matches Tuple."""

    src = textwrap.dedent("""
        from typing import NamedTuple, Tuple

        class C1(NamedTuple("nt", [("f1", int), ("f2", float)])):
          pass

        class C2(Tuple[int, float]):
          f1 = ...  # type: int
          f2 = ...  # type: float
        """)
    tree = self.Parse(src)

    nt = tree.Lookup("`nt`")
    c1 = tree.Lookup("C1")
    c2 = tree.Lookup("C2")

    self.assertEquals(c1.parents, (pytd.NamedType("`nt`"),))
    self.assertEquals(c2.Replace(name="`nt`"), nt)

  def testMetaclass(self):
    """Test parsing of metaclass kwarg."""
    self.TestRoundTrip(textwrap.dedent("""
      class C1(metaclass=foo):
          pass

      class C2(C1, metaclass=foo):
          pass
    """), textwrap.dedent("""
      class C1(metaclass=foo):
          pass

      class C2(C1, metaclass=foo):
          pass
    """))

  def testBadClassKwarg(self):
    """Test kwarg!=metaclass in classdef."""
    self.TestThrowsSyntaxError(textwrap.dedent("""
      class C(badword=foo):
          pass
    """))

    self.TestThrowsSyntaxError(textwrap.dedent("""
      class D:
          pass

      class C(D, badword=foo):
          pass
    """))

  def testAbstractMethod(self):
    """Test stripping of abstractmethod."""
    self.TestRoundTrip(textwrap.dedent("""
      from abc import abstractmethod, ABCMeta

      class C(metaclass=foo):
          @abstractmethod
          def foo(self) -> int: ...
    """), textwrap.dedent("""
      from abc import abstractmethod
      from abc import ABCMeta

      class C(metaclass=foo):
          def foo(self) -> int: ...
    """))

  def testTypeParameters(self):
    """Test parsing of type parameters."""
    src = textwrap.dedent("""
      T = TypeVar("T")
      T2 = TypeVar("T2")
      def f(x: T) -> T
      class A(Generic[T]):
        def a(self, x: T2) -> None:
          self := A[T or T2]
    """)
    tree = parser.TypeDeclParser().Parse(src)

    param1 = tree.Lookup("T")
    param2 = tree.Lookup("T2")
    self.assertEquals(param1, pytd.TypeParameter("T", scope=None))
    self.assertEquals(param2, pytd.TypeParameter("T2", scope=None))
    self.assertEquals(tree.type_params, (param1, param2))

    f = tree.Lookup("f")
    sig, = f.signatures
    p_x, = sig.params
    self.assertEquals(p_x.type, pytd.TypeParameter("T", scope=None))

    cls = tree.Lookup("A")
    cls_parent, = cls.parents
    f_cls, = cls.methods
    sig_cls, = f_cls.signatures
    # AdjustSelf has not been called yet, so self may not have the right type
    _, p_x_cls = sig_cls.params
    self.assertEquals(cls_parent.parameters,
                      (pytd.TypeParameter("T", scope=None),))
    self.assertEquals(p_x_cls.type, pytd.TypeParameter("T2", scope=None))

    # The parser should not have attempted to insert templates! It does
    # not know about imported type parameters.
    self.assertEquals(sig.template, ())
    self.assertEquals(cls.template, ())
    self.assertEquals(sig_cls.template, ())

  def testConvertTypingToNativeOnBuiltins(self):
    """Test typing to native conversion in parsing builtins."""
    builtins_src = textwrap.dedent("""
      class object():
        __dict__ = ...  # type: Dict[str, Any]

      class list(List): ...
      class itemiterator(Iterator): ...
    """)
    typing_src = textwrap.dedent("""
      class Pattern(object):
        def split(self) -> List
      class IO(Iterator): ...
    """)
    builtins = parser.parse_string(builtins_src, name="__builtin__")
    typing = parser.parse_string(typing_src, name="typing")

    # Things like constants and method returns should always be converted.
    constant = builtins.Lookup("__builtin__.object").Lookup("__dict__")
    self.assertEquals(pytd.NamedType("dict"), constant.type.base_type)

    method, = typing.Lookup("typing.Pattern").Lookup("split").signatures
    self.assertEquals(pytd.NamedType("list"), method.return_type)

    # Most parents should be converted for abstract matching to work.
    parent, = builtins.Lookup("__builtin__.itemiterator").parents
    self.assertEquals(pytd.NamedType("iterator"), parent)

    # Some parents should not be, to avoid circular class hierarchies.
    parent, = builtins.Lookup("__builtin__.list").parents
    self.assertEquals(pytd.NamedType("typing.List"), parent)

    parent, = typing.Lookup("typing.IO").parents
    self.assertEquals(pytd.NamedType("Iterator"), parent)


class TestDecorate(unittest.TestCase):
  """Test adding additional methods to nodes in a tree using decorate.py."""

  def testDecorator(self):
    decorator = decorate.Decorator()

    # Change pytd.NamedType to also have a method called "Test1"
    @decorator  # pylint: disable=unused-variable
    class NamedType(pytd.NamedType):

      def Test1(self):
        pass

    # Change pytd.Constant to also have a method called "Test2"
    @decorator  # pylint: disable=unused-variable
    class Constant(pytd.Constant):

      def Test2(self):
        pass

    tree = pytd.Constant("test", pytd.NamedType("test"))
    tree = decorator.Visit(tree)
    # test that we now have the "test2" method on pytd.Constant
    tree.Test2()
    # test that we now have the "test1" method on pytd.NamedType
    tree.type.Test1()

  def testDecoratorWithUndecoratedNodeType(self):
    decorator = decorate.Decorator()

    # Change pytd.NamedType to also have a method called "Test"
    @decorator  # pylint: disable=unused-variable
    class NamedType(pytd.NamedType):

      def Test(self):
        pass

    tree = pytd.Constant("test", pytd.NamedType("test"))
    # test that we don't crash on encountering pytd.Constant
    tree = decorator.Visit(tree)
    # test that we now have the "test" method on pytd.NamedType
    tree.type.Test()


if __name__ == "__main__":
  unittest.main()
