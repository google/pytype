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
from pytype.pytd.parse import parser_test_base
from pytype.pytd.parse import visitors
import unittest


# All of these tests implicitly test pytd.Print because
# parser_test_base.AssertSourceEquals() uses pytd.Print.


class TestVisitors(parser_test_base.ParserTest):
  """Tests the classes in parse/visitors."""

  def testInventStarArgsParams(self):
    call = lambda x: tuple(f.name for f in visitors.InventStarArgParams(x))
    self.assertEquals(("args", "kwargs"), call({}))
    self.assertEquals(("args", "kwargs"), call({"a"}))
    self.assertEquals(("_args", "kwargs"), call({"args"}))
    self.assertEquals(("args", "_kwargs"), call({"kwargs"}))
    self.assertEquals(("_args", "_kwargs"), call({"args", "kwargs"}))
    self.assertEquals(("__args", "_kwargs"), call({"args", "_args", "kwargs"}))
    self.assertEquals(("args", "__kwargs"), call({"kwargs", "_kwargs"}))

  def testLookupClasses(self):
    src = textwrap.dedent("""
        class object(object):
            pass

        class A(object):
            def a(self, a: A, b: B) -> A or B raises A, B

        class B(object):
            def b(self, a: A, b: B) -> A or B raises A, B
    """)
    tree = self.Parse(src)
    new_tree = visitors.LookupClasses(tree)
    self.AssertSourceEquals(new_tree, src)
    new_tree.Visit(visitors.VerifyLookup())

  def testMaybeInPlaceFillInClasses(self):
    src = textwrap.dedent("""
        class A(object):
            def a(self, a: A, b: B) -> A or B raises A, B
    """)
    tree = self.Parse(src)
    ty_a = pytd.ClassType("A")
    visitors.InPlaceFillInClasses(ty_a, tree)
    self.assertIsNotNone(ty_a.cls)
    ty_b = pytd.ClassType("B")
    visitors.InPlaceFillInClasses(ty_b, tree)
    self.assertIsNone(ty_b.cls)

  def testDefaceUnresolved(self):
    builtins = self.Parse(textwrap.dedent("""
      class int(object):
        pass
    """))
    src = textwrap.dedent("""
        class A(X):
            def a(self, a: A, b: X, c: int) -> X raises X
            def b(self) -> X[int]
    """)
    expected = textwrap.dedent("""
        class A(?):
            def a(self, a: A, b: ?, c: int) -> ? raises ?
            def b(self) -> ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    self.AssertSourceEquals(new_tree, expected)

  def testReplaceTypes(self):
    src = textwrap.dedent("""
        class A(object):
            def a(self, a: A or B) -> A or B raises A, B
    """)
    expected = textwrap.dedent("""
        class A(object):
            def a(self: A2, a: A2 or B) -> A2 or B raises A2, B
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.ReplaceTypes({"A": pytd.NamedType("A2")}))
    self.AssertSourceEquals(new_tree, expected)

  def testSuperClassesByName(self):
    src = textwrap.dedent("""
      class A():
          pass
      class B():
          pass
      class C(A):
          pass
      class D(A,B):
          pass
      class E(C,D,A):
          pass
    """)
    tree = self.Parse(src)
    data = tree.Visit(visitors.ExtractSuperClassesByName())
    self.assertItemsEqual(("classobj",), data["A"])
    self.assertItemsEqual(("classobj",), data["B"])
    self.assertItemsEqual(("A",), data["C"])
    self.assertItemsEqual(("A", "B"), data["D"])
    self.assertItemsEqual(("A", "C", "D"), data["E"])

  def testSuperClasses(self):
    src = textwrap.dedent("""
      class classobj:
          pass
      class A():
          pass
      class B():
          pass
      class C(A):
          pass
      class D(A,B):
          pass
      class E(C,D,A):
          pass
    """)
    ast = visitors.LookupClasses(self.Parse(src))
    data = ast.Visit(visitors.ExtractSuperClasses())
    self.assertItemsEqual(["classobj"], [t.name for t in data[ast.Lookup("A")]])
    self.assertItemsEqual(["classobj"], [t.name for t in data[ast.Lookup("B")]])
    self.assertItemsEqual(["A"], [t.name for t in data[ast.Lookup("C")]])
    self.assertItemsEqual(["A", "B"], [t.name for t in data[ast.Lookup("D")]])
    self.assertItemsEqual(["C", "D", "A"],
                          [t.name for t in data[ast.Lookup("E")]])

  def testStripSelf(self):
    src = textwrap.dedent("""
        def add(x: int, y: int) -> int
        class A(object):
            def bar(self, x: int) -> float
            def baz(self) -> float
            def foo(self, x: int, y: float) -> float
    """)
    expected = textwrap.dedent("""
        def add(x: int, y: int) -> int

        class A(object):
            def bar(x: int) -> float
            def baz() -> float
            def foo(x: int, y: float) -> float
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.StripSelf())
    self.AssertSourceEquals(new_tree, expected)

  def testRemoveUnknownClasses(self):
    src = textwrap.dedent("""
        class `~unknown1`():
            pass
        class `~unknown2`():
            pass
        class A(object):
            def foobar(x: `~unknown1`, y: `~unknown2`) -> `~unknown1` or int
    """)
    expected = textwrap.dedent("""
        class A(object):
            def foobar(x, y) -> ? or int
    """)
    tree = self.Parse(src)
    tree = tree.Visit(visitors.RemoveUnknownClasses())
    tree = tree.Visit(visitors.DropBuiltinPrefix())
    self.AssertSourceEquals(tree, expected)

  def testFindUnknownVisitor(self):
    src = textwrap.dedent("""
        class classobj:
          pass
        class `~unknown1`():
          pass
        class `~unknown_foobar`():
          pass
        class `~int`():
          pass
        class A():
          def foobar(self, x: `~unknown1`) -> ?
        class B():
          def foobar(self, x: `~int`) -> ?
        class C():
          x = ... # type: `~unknown_foobar`
        class D(`~unknown1`):
          pass
    """)
    tree = self.Parse(src)
    tree = visitors.LookupClasses(tree)
    find_on = lambda x: tree.Lookup(x).Visit(visitors.RaiseIfContainsUnknown())
    self.assertRaises(visitors.RaiseIfContainsUnknown.HasUnknown, find_on, "A")
    find_on("B")  # shouldn't raise
    self.assertRaises(visitors.RaiseIfContainsUnknown.HasUnknown, find_on, "C")
    self.assertRaises(visitors.RaiseIfContainsUnknown.HasUnknown, find_on, "D")

  def testCanonicalOrderingVisitor(self):
    src1 = textwrap.dedent("""
    def f() -> ? raises MemoryError, IOError
    def f(x: list[a]) -> ?
    def f(x: list[b or c]) -> ?
    def f(x: list[tuple[d]]) -> ?
    """)
    src2 = textwrap.dedent("""
    def f() -> ? raises IOError, MemoryError
    def f(x: list[tuple[d]]) -> ?
    def f(x: list[a]) -> ?
    def f(x: list[b or c]) -> ?
    """)
    tree1 = self.Parse(src1)
    tree1 = tree1.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    tree2 = self.Parse(src2)
    tree2 = tree2.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    self.AssertSourceEquals(tree1, tree2)

  def testInPlaceFillInExternalClasses(self):
    src1 = textwrap.dedent("""
      def f1() -> bar.Bar
      class Foo(object):
        pass
    """)
    src2 = textwrap.dedent("""
      def f2() -> foo.Foo
      class Bar(object):
        pass
    """)
    ast1 = self.Parse(src1)
    ast2 = self.Parse(src2)
    ast1 = ast1.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2)))
    ast2 = ast2.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2)))
    f1, = ast1.Lookup("f1").signatures
    f2, = ast2.Lookup("f2").signatures
    self.assertIs(ast2.Lookup("Bar"), f1.return_type.cls)
    self.assertIs(ast1.Lookup("Foo"), f2.return_type.cls)

  def testInPlaceLookupExternalClassesByFullName(self):
    src1 = textwrap.dedent("""
      def f1() -> bar.Bar
      class Foo(object):
        pass
    """)
    src2 = textwrap.dedent("""
      def f2() -> foo.Foo
      class Bar(object):
        pass
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast1 = ast1.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2),
                                                   full_names=True))
    ast2 = ast2.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2),
                                                   full_names=True))
    f1, = ast1.Lookup("foo.f1").signatures
    f2, = ast2.Lookup("bar.f2").signatures
    self.assertIs(ast2.Lookup("bar.Bar"), f1.return_type.cls)
    self.assertIs(ast1.Lookup("foo.Foo"), f2.return_type.cls)

  def testCollectDependencies(self):
    src = textwrap.dedent("""
      l = ... # type: list[int or baz.BigInt]
      def f1() -> bar.Bar
      def f2() -> foo.bar.Baz
    """)
    deps = visitors.CollectDependencies()
    self.Parse(src).Visit(deps)
    self.assertSetEqual({"baz", "bar", "foo.bar"}, deps.modules)

  def testExpand(self):
    src = textwrap.dedent("""
        def foo(a: int or float, z: complex or str, u: bool) -> file
        def bar(a: int) -> str or unicode
    """)
    new_src = textwrap.dedent("""
        def foo(a: int, z: complex, u: bool) -> file
        def foo(a: int, z: str, u: bool) -> file
        def foo(a: float, z: complex, u: bool) -> file
        def foo(a: float, z: str, u: bool) -> file
        def bar(a: int) -> str or unicode
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, visitors.ExpandSignatures()),
        new_src)

  def testPrintImports(self):
    no_import_src = textwrap.dedent("""
      def f(x: Union[int, slice]) -> List[Any]: ...
      def g(x: foo.C.C2) -> None: ...
    """)
    imports = textwrap.dedent("""
      import foo.C
      from typing import Any, List, Union
    """)
    expected_src = (imports + no_import_src).strip()  # Extra newlines

    tree = self.Parse(no_import_src)
    res = tree.Visit(visitors.PrintVisitor())

    # AssertSourceEquals strips imports
    self.AssertSourceEquals(res, no_import_src)
    self.assertMultiLineEqual(res, expected_src)

  def testPrintImportsNamedType(self):
    # Can't get tree by parsing so build explicitly
    node = pytd.Constant("x", pytd.NamedType("typing.List"))
    tree = pytd.TypeDeclUnit(constants=(node,), type_params=(),
                             functions=(), classes=(), aliases=(), name=None)

    expected_src = textwrap.dedent("""
      import typing

      x = ...  # type: typing.List
    """).strip()
    res = tree.Visit(visitors.PrintVisitor())
    self.assertMultiLineEqual(res, expected_src)

  def testPrintImportsIgnoresExisting(self):
    src = "from foo import b"

    tree = self.Parse(src)
    res = tree.Visit(visitors.PrintVisitor())
    self.assertMultiLineEqual(res, src)

  def testAdjustTypeParameters(self):
    ast = self.Parse("""
      T = TypeVar("T")
      T2 = TypeVar("T2")
      def f(x: T) -> T
      class A(Generic[T]):
        def a(self, x: T2) -> None:
          self := A[T or T2]
    """)

    f = ast.Lookup("f")
    sig, = f.signatures
    p_x, = sig.params
    self.assertEquals(sig.template,
                      (pytd.TemplateItem(pytd.TypeParameter("T", "f")),))
    self.assertEquals(p_x.type, pytd.TypeParameter("T", "f"))

    cls = ast.Lookup("A")
    f_cls, = cls.methods
    sig_cls, = f_cls.signatures
    p_self, p_x_cls = sig_cls.params
    self.assertEquals(cls.template,
                      (pytd.TemplateItem(pytd.TypeParameter("T", "A")),))
    self.assertEquals(sig_cls.template,
                      (pytd.TemplateItem(pytd.TypeParameter("T2", "A.a")),))
    self.assertEquals(p_self.type.parameters, (pytd.TypeParameter("T", "A"),))
    self.assertEquals(p_x_cls.type, pytd.TypeParameter("T2", "A.a"))

  def testAdjustTypeParametersWithBuiltins(self):
    ast = self.ParseWithBuiltins("""
      T = TypeVar("T")
      K = TypeVar("K")
      V = TypeVar("V")
      class Foo(List[int]): pass
      class Bar(Dict[T, int]): pass
      class Baz(Generic[K, V]): pass
      class Qux(Baz[str, int]): pass
    """)
    foo = ast.Lookup("Foo")
    bar = ast.Lookup("Bar")
    qux = ast.Lookup("Qux")
    foo_parent, = foo.parents
    bar_parent, = bar.parents
    qux_parent, = qux.parents
    # Expected:
    #  Class(Foo, parent=GenericType(List, parameters=(int,)), template=())
    #  Class(Bar, parent=GenericType(Dict, parameters=(T, int)), template=(T))
    #  Class(Qux, parent=GenericType(Baz, parameters=(str, int)), template=())
    self.assertEquals((pytd.ClassType("int"),), foo_parent.parameters)
    self.assertEquals((), foo.template)
    self.assertEquals((pytd.TypeParameter("T", "Bar"), pytd.ClassType("int")),
                      bar_parent.parameters)
    self.assertEquals((pytd.TemplateItem(pytd.TypeParameter("T", "Bar")),),
                      bar.template)
    self.assertEquals((pytd.ClassType("str"), pytd.ClassType("int")),
                      qux_parent.parameters)
    self.assertEquals((), qux.template)

  def testVerifyContainers(self):
    ast1 = self.ParseWithBuiltins("""
      T = TypeVar("T")
      class Foo(SupportsInt[T]): pass
    """)
    ast2 = self.ParseWithBuiltins("""
      class Foo(SupportsInt[int]): pass
    """)
    ast3 = self.ParseWithBuiltins("""
      class Foo(Generic[int]): pass
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast1.Visit(visitors.VerifyContainers()))
    self.assertRaises(visitors.ContainerError,
                      lambda: ast2.Visit(visitors.VerifyContainers()))
    self.assertRaises(visitors.ContainerError,
                      lambda: ast3.Visit(visitors.VerifyContainers()))


if __name__ == "__main__":
  unittest.main()
