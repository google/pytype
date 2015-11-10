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
from pytype.pytd.parse import parser_test
import unittest


class TestASTGeneration(parser_test.ParserTest):

  def TestThrowsSyntaxError(self, src):
    self.assertRaises((SyntaxError, SystemError), self.parser.Parse, src)

  def TestRoundTrip(self, src, canonical_src=None, check_the_sourcecode=True):
    """Compile a string, and convert the result back to a string. Compare."""
    if canonical_src is None:
      canonical_src = src
    tree = self.Parse(src)
    new_src = pytd.Print(tree)
    self.AssertSourceEquals(new_src, canonical_src)
    if check_the_sourcecode:
      self.assertMultiLineEqual(new_src.rstrip().lstrip("\n"),
                                canonical_src.rstrip().lstrip("\n"))

  def testImport(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        import abc
        import abc.efg
        from abc import a, b, c
        from abc.efg import e, f, g
        from abc import a as aa, b as bb, c
        from abc.efg import a as aa, b as bb, c
        from abc import *
        from abc.efg import *
        """)
    self.TestRoundTrip(src, "")  # Imports are not part of the AST

  def testImportErrors(self):
    """Test import errors."""
    self.assertRaises(textwrap.dedent("""
        import abc as efg
    """))
    self.assertRaises(textwrap.dedent("""
        import abc.efg as efg
    """))

  def testRenaming(self):
    """Test parsing of import."""
    src = textwrap.dedent("""
        from foobar import SomeClass
        class A(SomeClass): ...
        """)
    self.TestRoundTrip(src, textwrap.dedent("""
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
        def foo(a: int, c: bool) -> int raises Foo, Test
        """)
    self.TestRoundTrip(src)

  def testBackticks(self):
    """Test parsing of names in backticks."""
    src = textwrap.dedent("""
      def `foo-bar`(x: `~unknown3`) -> `funny-type`[int]
      """)
    self.TestRoundTrip(src)

  def testOneDottedFunction(self):
    """Test parsing of a single function with dotted names."""
    # We won't normally use __builtins__ ... this is just for testing.
    src = textwrap.dedent("""
        def foo(a: __builtins__.int) -> __builtins__.int raises foo.Foo
        def qqsv(x_or_y: compiler.symbols.types.BooleanType) -> NoneType
        """)
    self.TestRoundTrip(src)

  def testEllipsis1(self):
    """Test parsing of function bodies."""
    src = textwrap.dedent("""
        def f(x) -> None: ...
        def f(x) -> None:
          ...
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

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
        def eval(s: str) -> Any
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testQuotes(self):
    """Test parsing of quoted types."""
    src = textwrap.dedent("""
        def occurences() -> "Dict[str, List[int]]"
        class A(object): ...
        def invert(d: 'Dict[A, A]') -> 'Dict[A, A]'
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testCallable(self):
    """Test parsing Callable."""
    src = textwrap.dedent("""
        def get_listener() -> Callable[[int, int], str]"
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testAlias(self):
    """Test parsing Callable."""
    src = textwrap.dedent("""
        StrDict = Dict[str, str]
        def get_listener(x: StrDict) -> StrDict
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testDecorator(self):
    """Test overload decorators."""
    src = textwrap.dedent("""
        @overload
        def abs(x: int) -> int
        @overload
        def abs(x: float) -> float

        class A(object):
          @overload
          def abs(self, x: int, y: int) -> int
          @overload
          def abs(self, x: float, y: float) -> float
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

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
        def f() -> List[int, ...]
    """)
    self.TestRoundTrip(src)

  def testGeneric(self):
    src = textwrap.dedent("""
        X = TypeVar('X')
        class T1(typing.Generic[X], object):
            pass

        X = TypeVar('X')
        Y = TypeVar('Y')
        class T2(typing.Generic[X, Y], T1):
            pass

        X = TypeVar('X')
        Y = TypeVar('Y')
        class T3(typing.Generic[X, Y], T1, T2):
            pass
    """)
    self.TestRoundTrip(src)

  def testTemplated(self):
    src = textwrap.dedent("""
        def foo(x: int) -> T1[float, ...]
        def foo(x: int) -> T2[int, complex]
        def foo(x: int) -> T3[int, T4[str]]
        def bar(y: int) -> T1[float]
        T = TypeVar('T')
        def qqsv(x: T) -> List[T, ...]
        S = TypeVar('S')
        T = TypeVar('T')
        def qux(x: T) -> List[S]

        X = TypeVar('X')
        class T1(typing.Generic[X], object):
            def foo(a: X) -> T2[X, int] raises float

        X = TypeVar('X')
        Y = TypeVar('Y')
        class T2(typing.Generic[X, Y], object):
            def foo(a: X) -> complex raises Except[X, Y]
    """)
    self.TestRoundTrip(src)

  def testOptionalParameters(self):
    """Test parsing of individual optional parameters."""
    src = textwrap.dedent("""
        def f(x) -> int
        def f(x = ...) -> int
        def f(x: int = ...) -> int
        def f(x, s: str = ..., t: str = ...) -> int
        """)
    self.TestRoundTrip(src, check_the_sourcecode=False)

  def testOnlyOptional(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(...) -> int
    """).strip()
    self.TestRoundTrip(src)

  def testOptional1(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(a: int, ...) -> int
    """).strip()
    self.TestRoundTrip(src)

  def testOptional2(self):
    """Test parsing of optional parameters."""
    src = textwrap.dedent("""
        def foo(a: int, c: bool, ...) -> int
    """).strip()
    self.TestRoundTrip(src)

  def testConstants(self):
    """Test parsing of constants."""
    src = textwrap.dedent("""
      a = ...  # type: int
      b = ...  # type: int or float
    """).strip()
    self.TestRoundTrip(src)

  def testReturnTypes(self):
    src = textwrap.dedent("""
        def a() -> ?  # TODO(pludemann): remove "-> ?" if we allow implicit result
        def b() -> ?
        def c() -> object
        def d() -> None
        def e() -> a or b
        def f() -> a[x, ...]
        def g() -> a[x]
        def h() -> a[x,y]
        def i() -> nothing  # never returns
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
        def foo(a: int or float, c: bool) -> List[int] raises Foo, Test
    """)
    self.TestRoundTrip(src)

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
        def baz(i: int) -> ?
    """)
    result = self.Parse(src)
    foo = result.Lookup("Foo")
    self.assertEquals(["bar"], [f.name for f in foo.methods])
    self.assertEquals(["baz"], [f.name for f in result.functions])

  def testFunctionTypeParams(self):
    src = textwrap.dedent("""
        T1 = TypeVar('T1')
        def f(x: T1) -> T1
    """)
    self.TestRoundTrip(src)

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
        def baz(i: X) -> ?:
            i := X

        class Foo(object):
            c = ...  # type: int
            def bar(x: X) -> ?:
                x := X
    """)
    self.TestRoundTrip(src, dest)

  def testDuplicates3(self):
    src = textwrap.dedent("""
        class A(typing.Generic[T, T], object):
          pass
    """)
    self.TestThrowsSyntaxError(src)

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
        def x()
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates8(self):
    src = textwrap.dedent("""
       def bar(x: int) -> NoneType
       def foo PYTHONCODE
       def bar(x: float) -> str
       def foo PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates8b(self):
    src = textwrap.dedent("""
    class Foo(object):
       def bar(x: int) -> NoneType
       def foo PYTHONCODE
       def bar(x: float) -> str
       def foo PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates9(self):
    src = textwrap.dedent("""
       def bar(x: int) -> NoneType
       def bar PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates9b(self):
    src = textwrap.dedent("""
    class Foo(object):
       def bar(x: int) -> NoneType
       def bar PYTHONCODE
    """)
    self.TestThrowsSyntaxError(src)

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
    self.assertIsInstance(append_int.params[0], pytd.MutableParameter)
    self.assertIsInstance(append_float.params[0], pytd.MutableParameter)

  def testMutableOptional(self):
    src = textwrap.dedent("""
        def append_float(l: list = ...) -> int:
          l := list[float]
    """)
    self.TestThrowsSyntaxError(src)

  def testMutableRoundTrip(self):
    src = textwrap.dedent("""
        def append_float(l: list) -> ?:
            l := List[float]

        class Foo(object):
            def append_int(l: list) -> ?:
                l := List[int]
    """)
    self.TestRoundTrip(src)

  def testExternalTypes(self):
    """Test parsing of names with dots."""
    src = textwrap.dedent("""
      a = ... # type: Foo
      b = ... # type: x.Bar
      c = ... # type: x.y.Baz
      """)
    result = self.Parse(src)
    self.assertEquals(pytd.NamedType("Foo"), result.Lookup("a").type)
    self.assertEquals(pytd.ExternalType("Bar", "x"), result.Lookup("b").type)
    self.assertEquals(pytd.ExternalType("Baz", "x.y"), result.Lookup("c").type)

  def testMultiFunction(self):
    """Test parsing of multiple function defs including overloaded version."""

    data = textwrap.dedent("""
        # several function defs with different sigs
        def foo(a : int, c : bool) -> int raises Test, Foo
        def foo() -> None
        def add(x : int, y : int) -> int
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
        def foo(a: int, b: int or float or None, c: Foo and `s`.`Bar` and Zot) -> int raises Bad
    """)
    data1 = textwrap.dedent("""
        def foo(a: int, b: int or float or None, c: Foo and s.Bar and Zot) -> int raises Bad
    """)
    data2 = textwrap.dedent("""
        def foo(a: int, b: int or (float or None), c: Foo and (s.Bar and Zot)) -> int raises Bad
    """)
    data3 = textwrap.dedent("""
        def foo(a: int, b: (int or float) or None, c: (Foo and s.Bar) and Zot) -> int raises Bad
    """)
    data4 = textwrap.dedent("""
        def foo(a: int, b: ((((int or float)) or ((None)))), c: (((Foo) and s.Bar and (Zot)))) -> int raises Bad
    """)

    self.TestRoundTrip(data1, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data2, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data3, canonical, check_the_sourcecode=False)
    self.TestRoundTrip(data4, canonical, check_the_sourcecode=False)

  def testComplexCombinedType(self):
    """Test parsing a type with both union and intersection."""

    data1 = r"def foo(a: Foo or Bar and Zot) -> object"
    data2 = r"def foo(a: Foo or (Bar and Zot)) -> object"
    result1 = self.Parse(data1)
    result2 = self.Parse(data2)
    f = pytd.Function(
        name="foo",
        signatures=(pytd.Signature(
            params=(
                pytd.Parameter(
                    name="a",
                    type=pytd.UnionType(
                        type_list=(
                            pytd.NamedType("Foo"),
                            pytd.IntersectionType(
                                type_list=(
                                    pytd.NamedType("Bar"),
                                    pytd.NamedType("Zot"))))
                    )
                ),),
            return_type=pytd.NamedType("object"),
            template=(), has_optional=False,
            exceptions=()),))
    self.assertEqual(f, result1.Lookup("foo"))
    self.assertEqual(f, result2.Lookup("foo"))

  def testNoReturnType(self):
    """Test a parsing error (no return type)."""

    data1 = "def foo() -> ?"
    data2 = "def foo() -> NoneType"

    self.TestRoundTrip(data1)
    self.TestRoundTrip(data2)

  def testVersionSplitFunction(self):
    """Test version conditionals."""
    data = textwrap.dedent("""
    if python < 3:
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
      if python > 2.7.3:
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
    if python < 3:
      c1 = ...  # type: int
    if python < 3.1:
      c2 = ...  # type: int
    if python < 3.1.1:
      c3 = ...  # type: int
    if python <= 3:
      c4 = ...  # type: int
    if python <= 3.1:
      c5 = ...  # type: int
    if python <= 3.1.1:
      c6 = ...  # type: int
    if python > 3:
      c7 = ...  # type: int
    if python > 3.1:
      c8 = ...  # type: int
    if python > 3.1.1:
      c9 = ...  # type: int
    if python >= 3:
      c10 = ...  # type: int
    if python >= 3.1:
      c11 = ...  # type: int
    if python >= 3.1.1:
      c12 = ...  # type: int
    if python == 3.0.0:
      c13 = ...  # type: int
    if python != 3.0.0:
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
    if python <= 3:
      c1 = ...  # type: int
    if python <= 3.0:
      c2 = ...  # type: int
    if python <= 3.0.0:
      c3 = ...  # type: int
    if python > 3:
      c4 = ...  # type: int
    if python > 3.0:
      c5 = ...  # type: int
    if python > 3.0.0:
      c6 = ...  # type: int
    """)
    unit = self.Parse(data, version=(3, 0, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["c1", "c2", "c3"])
    unit = self.Parse(data, version=(3, 0, 1))
    self.assertEquals([f.name for f in unit.constants],
                      ["c4", "c5", "c6"])

  def testTemplateSimple(self):
    """Test simple class template."""
    data = textwrap.dedent("""
        T = TypeVar('T')
        class MyClass(typing.Generic[T], object):
            def f(self, T) -> T
        """)
    self.TestRoundTrip(data)

  def testTemplateNameReuseOnClass(self):
    """Test name reuse between templated classes."""
    data = textwrap.dedent("""
        T = TypeVar('T')
        class MyClass1(typing.Generic[T], object):
            def f(self, T) -> T

        T = TypeVar('T')
        class MyClass2(typing.Generic[T], object):
            def f(self, T) -> T
        """)
    self.TestRoundTrip(data)

  def testTemplateNameReuseOnMethods(self):
    """Test name reuse between methods."""
    data = textwrap.dedent("""
        T = TypeVar('T')
        V = TypeVar('V')
        class MyClass1(typing.Generic[T], object):
            def f(self, T, V) -> V

        T = TypeVar('T')
        class MyClass2(typing.Generic[T], object):
            def f(self, T, V) -> V
        """)
    self.TestRoundTrip(data, check_the_sourcecode=False)

  def testScopedTypevar(self):
    """Test type parameters as class attributes."""
    data = textwrap.dedent("""
        class MyClass1(object):
            SomeType = TypeVar('SomeType')
            def g(x: SomeType) -> SomeType
        def f(x: SomeType) -> SomeType
        """)
    self.TestRoundTrip(data, textwrap.dedent("""
        def f(x: SomeType) -> SomeType

        class MyClass1(object):
            SomeType = TypeVar('SomeType')
            def g(x: SomeType) -> SomeType
        """))

  def testTypeVarReuseOnGlobalMethods(self):
    """Test two global methods sharing a type variable."""
    data = textwrap.dedent("""
        T = TypeVar('T')
        def f(x: T) -> T
        def g(x: T) -> T
        """)
    self.TestRoundTrip(data, textwrap.dedent("""
        T = TypeVar('T')
        def f(x: T) -> T
        T = TypeVar('T')
        def g(x: T) -> T
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

  def testSelf(self):
    """Test handling of self."""

    data = textwrap.dedent("""
        U = TypeVar('U')
        V = TypeVar('V')
        class MyClass(typing.Generic[U, V], object):
          def f1(self) -> ?
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
        def foo(a: List[bool], b: X or Y) -> Z:
            a := List[int]
        def bar(a: int, b: List[int]) -> Z:
            b := List[complex]
        def bar(a: int, b: List[float]) -> Z:
            b := List[str]""")
    self.TestRoundTrip(src)

  def testTypeCommentSpaces(self):
    """Test types in comments."""
    self.TestRoundTrip(textwrap.dedent("""
      x = ...  # type: List[int]
      y = ... # type: int
      z = ...# type: float
    """), textwrap.dedent("""
      x = ...  # type: List[int]
      y = ...  # type: int
      z = ...  # type: float
    """))


class TestDecorate(unittest.TestCase):
  """Test adding additional methods to nodes in a tree using decorate.py."""

  def testDecorator(self):
    decorator = decorate.Decorator()

    # Change pytd.NamedType to also have a method called "Test1"
    @decorator  # pylint: disable=unused-variable
    class NamedType(pytd.NamedType):

      def Test1(self):
        pass

    # Change pytd.Scalar to also have a method called "Test2"
    @decorator  # pylint: disable=unused-variable
    class Scalar(pytd.Scalar):

      def Test2(self):
        pass

    tree = pytd.Scalar(pytd.NamedType("test"))
    tree = decorator.Visit(tree)
    # test that we now have the "test2" method on pytd.Scalar
    tree.Test2()
    # test that we now have the "test1" method on pytd.NamedType
    tree.value.Test1()

  def testDecoratorWithUndecoratedNodeType(self):
    decorator = decorate.Decorator()

    # Change pytd.NamedType to also have a method called "Test"
    @decorator  # pylint: disable=unused-variable
    class NamedType(pytd.NamedType):

      def Test(self):
        pass

    tree = pytd.Scalar(pytd.NamedType("test"))
    # test that we don't crash on encountering pytd.Scalar
    tree = decorator.Visit(tree)
    # test that we now have the "test" method on pytd.NamedType
    tree.value.Test()


if __name__ == "__main__":
  unittest.main()
