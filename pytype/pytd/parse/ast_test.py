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

  def TestRoundTrip(self, src, canonical_src=None):
    """Compile a string, and convert the result back to a string. Compare."""
    tree = self.Parse(src)
    new_src = pytd.Print(tree)
    self.AssertSourceEquals(new_src, (canonical_src or src))

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
      def `foo-bar`(x: `~unknown3`) -> `funny-type`<int>
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

  def testTemplated(self):
    src = textwrap.dedent("""
        def foo(x: int) -> T1<float>
        def foo(x: int) -> T2<int, complex>
        def foo(x: int) -> T3<int, T4<str>>
        def bar(y: int) -> T1<float,>
        def qqsv<T>(x: T) -> list<T>
        def qux<S,T>(x: T) -> list<S,>

        class T1<X>:
            def foo(a: X) -> T2<X, int> raises float

        class T2<X, Y>:
            def foo(a: X) -> complex raises Except<X, Y>
    """)
    self.TestRoundTrip(src)

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

  def testOptionalWithSpaces(self):
    """Test parsing of ... with spaces."""
    # Python supports this, so we do, too.
    self.TestRoundTrip("def foo(a: int, c: bool, . . .) -> int",
                       "def foo(a: int, c: bool, ...) -> int")

  def testConstants(self):
    """Test parsing of constants."""
    src = textwrap.dedent("""
      a: int
      b: int or float
    """).strip()
    self.TestRoundTrip(src)

  def testReturnTypes(self):
    src = textwrap.dedent("""
        def a() -> ?  # TODO(pludemann): remove "-> ?" if we allow implicit result
        def b() -> ?
        def c() -> object
        def d() -> None
        def e() -> a or b
        def f() -> a<x>
        def g() -> a<x,>
        def h() -> a<x,y>
        def i() -> nothing  # never returns
    """)
    result = self.Parse(src)
    ret = {f.name: f.signatures[0].return_type for f in result.functions}
    self.assertIsInstance(ret["a"], pytd.AnythingType)
    self.assertIsInstance(ret["b"], pytd.AnythingType)
    self.assertEquals(ret["c"], pytd.NamedType("object"))
    self.assertEquals(ret["d"], pytd.NamedType("None"))
    self.assertIsInstance(ret["e"], pytd.UnionType)
    self.assertIsInstance(ret["f"], pytd.HomogeneousContainerType)
    self.assertIsInstance(ret["g"], pytd.GenericType)
    self.assertIsInstance(ret["h"], pytd.GenericType)
    self.assertIsInstance(ret["i"], pytd.NothingType)

  def testTemplateReturn(self):
    src = textwrap.dedent("""
        def foo(a: int or float, c: bool) -> list<int> raises Foo, Test
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
        class Foo:
          def bar() -> ?
        def baz(i: int) -> ?
    """)
    result = self.Parse(src)
    foo = result.Lookup("Foo")
    self.assertEquals(["bar"], [f.name for f in foo.methods])
    self.assertEquals(["baz"], [f.name for f in result.functions])

  def testSpaces(self):
    """Test that start-of-file / end-of-file whitespace is handled correctly."""
    self.TestRoundTrip("x: int")
    self.TestRoundTrip("x: int\n")
    self.TestRoundTrip("\nx: int")
    self.TestRoundTrip("\nx: int")
    self.TestRoundTrip("\n\nx: int")
    self.TestRoundTrip("  \nx: int")
    self.TestRoundTrip("x: int  ")
    self.TestRoundTrip("x: int  \n")
    self.TestRoundTrip("x: int\n  ")
    self.TestRoundTrip("x: int\n\n")

  def testSpacesWithIndent(self):
    self.TestRoundTrip("def f(x: list<nothing>) -> ?:\n    x := list<int>")
    self.TestRoundTrip("\ndef f(x: list<nothing>) -> ?:\n    x := list<int>")
    self.TestRoundTrip("\ndef f(x: list<nothing>) -> ?:\n    x := list<int>  ")
    self.TestRoundTrip("def f(x: list<nothing>) -> ?:\n    x := list<int>  \n")
    self.TestRoundTrip("def f(x: list<nothing>) -> ?:\n    x := list<int>\n  ")

  def testAlignedComments(self):
    src = textwrap.dedent("""
        # comment 0
        class Foo: # eol line comment 0
          # comment 1
          def bar(x: list<nothing>) -> ?: # eol line comment 1
            # comment 2
            x := list<float> # eol line comment 2
            # comment 3
          # comment 4
        # comment 5
        def baz(i: list<nothing>) -> ?: # eol line comment 3
          # comment 6
          i := list<int> # eol line comment 4
          # comment 7
        # comment 8
    """)
    dest = textwrap.dedent("""
        def baz(i: list<nothing>) -> ?:
            i := list<int>

        class Foo:
            def bar(x: list<nothing>) -> ?:
                x := list<float>
    """)
    self.TestRoundTrip(src, dest)

  def testUnalignedComments(self):
    src = textwrap.dedent("""
          # comment 0
        class Foo:
            # comment 1
          def bar(x: X) -> ?:
              # comment 2
            x := X # eol line comment 2
               # comment 3
         # comment 4
          c: int
        def baz(i: X) -> ?:
           # comment 6
          i := X
            # comment 6
    """)
    dest = textwrap.dedent("""
        def baz(i: X) -> ?:
            i := X

        class Foo:
            c: int
            def bar(x: X) -> ?:
                x := X
    """)
    self.TestRoundTrip(src, dest)

  def testDuplicates1(self):
    src = textwrap.dedent("""
        def baz<T, T>(i: int)
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates2(self):
    src = textwrap.dedent("""
        class A<T>:
          def baz<T>(i: int)
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates3(self):
    src = textwrap.dedent("""
        class A<T, T>:
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates4(self):
    src = textwrap.dedent("""
        class A:
          pass
        class A:
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates5(self):
    src = textwrap.dedent("""
        def x()
        class x:
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates6(self):
    src = textwrap.dedent("""
        x = int
        class x:
          pass
    """)
    self.TestThrowsSyntaxError(src)

  def testDuplicates7(self):
    src = textwrap.dedent("""
        x = int
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
    class Foo:
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
    class Foo:
      def bar PYTHONCODE
    """)
    self.TestRoundTrip(src)

  def testMutable(self):
    src = textwrap.dedent("""
        class Foo:
          def append_int(l: list) -> ?:
            l := list<int>
        def append_float(l: list) -> ?:
          l := list<float>
    """)
    module = self.Parse(src)
    foo = module.Lookup("Foo")
    self.assertEquals(["append_int"], [f.name for f in foo.methods])
    self.assertEquals(["append_float"], [f.name for f in module.functions])
    append_int = foo.methods[0].signatures[0]
    append_float = module.functions[0].signatures[0]
    self.assertIsInstance(append_int.params[0], pytd.MutableParameter)
    self.assertIsInstance(append_float.params[0], pytd.MutableParameter)

  def testMutableRoundTrip(self):
    src = textwrap.dedent("""
        def append_float(l: list) -> ?:
            l := list<float>

        class Foo:
            def append_int(l: list) -> ?:
                l := list<int>
    """)
    self.TestRoundTrip(src)

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
    self.assertEquals(sig1.return_type.name, "None")
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

    self.TestRoundTrip(data1, canonical)
    self.TestRoundTrip(data2, canonical)
    self.TestRoundTrip(data3, canonical)
    self.TestRoundTrip(data4, canonical)

  def testComplexCombinedType(self):
    """Test parsing a type with both union and intersection."""

    data1 = r"def foo(a: Foo or Bar and Zot) -> object"
    data2 = r"def foo(a: Foo or (Bar and Zot)) -> object"
    result1 = self.Parse(data1)
    result2 = self.Parse(data2)
    f = pytd.FunctionWithSignatures(
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

  def testTokens(self):
    """Test various token forms (int, float, n"...", etc.)."""
    # TODO(pludemann): a test with '"' or "'" in a string
    data = textwrap.dedent("""
        def `interface`(abcde: "xyz", foo: 'a"b', b: -1.0, c: 666) -> int
        """)

    result = self.Parse(data)
    f1 = result.Lookup("interface")
    f2 = pytd.FunctionWithSignatures(
        name="interface",
        signatures=(pytd.Signature(
            params=(
                pytd.Parameter(name="abcde",
                               type=pytd.Scalar(value="xyz")),
                pytd.Parameter(name="foo",
                               type=pytd.Scalar(value='a"b')),
                pytd.Parameter(name="b",
                               type=pytd.Scalar(value=-1.0)),
                pytd.Parameter(name="c",
                               type=pytd.Scalar(value=666))),
            return_type=pytd.NamedType("int"),
            exceptions=(),
            template=(), has_optional=False),))
    self.assertEqual(f1, f2)

  def testNoReturnType(self):
    """Test a parsing error (no return type)."""

    data1 = "def foo() -> ?"
    data2 = "def foo() -> None"

    self.TestRoundTrip(data1)
    self.TestRoundTrip(data2)

  def testVersionSplitFunction(self):
    """Test version conditionals."""
    data = textwrap.dedent("""
    if python < 3:
      c1: int
      def f() -> ?
      class A:
        pass
    else:
      c2: int
      def g() -> ?
      class B:
        pass

    class Foo:
      if python > 2.7.3:
        attr2 : int
        def m2() -> ?
      else:
        attr1 : int
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
      c1: int
    if python < 3.1:
      c2: int
    if python < 3.1.1:
      c3: int
    if python <= 3:
      c4: int
    if python <= 3.1:
      c5: int
    if python <= 3.1.1:
      c6: int
    if python > 3:
      c7: int
    if python > 3.1:
      c8: int
    if python > 3.1.1:
      c9: int
    if python >= 3:
      c10: int
    if python >= 3.1:
      c11: int
    if python >= 3.1.1:
      c12: int
    if python == 3.0.0:
      c13: int
    if python != 3.0.0:
      c14: int
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
      c1: int
    if python <= 3.0:
      c2: int
    if python <= 3.0.0:
      c3: int
    if python > 3:
      c4: int
    if python > 3.0:
      c5: int
    if python > 3.0.0:
      c6: int
    """)
    unit = self.Parse(data, version=(3, 0, 0))
    self.assertEquals([f.name for f in unit.constants],
                      ["c1", "c2", "c3"])
    unit = self.Parse(data, version=(3, 0, 1))
    self.assertEquals([f.name for f in unit.constants],
                      ["c4", "c5", "c6"])

  def testTemplates(self):
    """Test template parsing."""

    data = textwrap.dedent("""
        class MyClass<C>:
          def f1(p1: C) -> ?
          def f2<T,U>(p1: C, p2: T, p3: dict<C, C or T or int>) -> T raises Error<T>
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
    self.assertEquals([t.name for t in f2.template], ["T", "U"])
    p1, p2, p3 = f2.params
    t1, t2, t3 = p1.type, p2.type, p3.type
    self.assertIsInstance(t1, pytd.TypeParameter)
    self.assertIsInstance(t2, pytd.TypeParameter)
    self.assertNotIsInstance(t3, pytd.TypeParameter)
    self.assertEquals(t3.base_type.name, "dict")
    self.assertIsInstance(f2.return_type, pytd.TypeParameter)
    self.assertEquals(f2.return_type.name, "T")
    self.assertEquals(len(f2.exceptions), 1)
    self.assertEquals(len(f2.template), 2)

  def testSelf(self):
    """Test handling of self."""

    data = textwrap.dedent("""
        class MyClass<U, V>:
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
        def foo(a: list<bool>, b: X or Y) -> Z:
            a := list<int>
        def bar(a: int, b: list<int>) -> Z:
            b := list<complex>
        def bar(a: int, b: list<float>) -> Z:
            b := list<str>""")
    self.TestRoundTrip(src)


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


if __name__ == "__main__":
  unittest.main()
