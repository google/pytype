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
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.pytd.parse import parser_test_base
import unittest


# All of these tests implicitly test pytd.Print because
# parser_test_base.AssertSourceEquals() uses pytd.Print.


class TestVisitors(parser_test_base.ParserTest):
  """Tests the classes in parse/visitors."""

  def testInventStarArgsParams(self):
    call = lambda x: tuple(f.name for f in visitors.InventStarArgParams(x))
    self.assertEqual(("args", "kwargs"), call({}))
    self.assertEqual(("args", "kwargs"), call({"a"}))
    self.assertEqual(("_args", "kwargs"), call({"args"}))
    self.assertEqual(("args", "_kwargs"), call({"kwargs"}))
    self.assertEqual(("_args", "_kwargs"), call({"args", "kwargs"}))
    self.assertEqual(("__args", "_kwargs"), call({"args", "_args", "kwargs"}))
    self.assertEqual(("args", "__kwargs"), call({"kwargs", "_kwargs"}))

  def testLookupClasses(self):
    src = textwrap.dedent("""
        class object(object):
            pass

        class A(object):
            def a(self, a: A, b: B) -> A or B:
                raise A()
                raise B()

        class B(object):
            def b(self, a: A, b: B) -> A or B:
                raise A()
                raise B()
    """)
    tree = self.Parse(src)
    new_tree = visitors.LookupClasses(tree)
    self.AssertSourceEquals(new_tree, src)
    new_tree.Visit(visitors.VerifyLookup())

  def testMaybeFillInLocalPointers(self):
    src = textwrap.dedent("""
        class A(object):
            def a(self, a: A, b: B) -> A or B:
                raise A()
                raise B()
    """)
    tree = self.Parse(src)
    ty_a = pytd.ClassType("A")
    ty_a.Visit(visitors.FillInLocalPointers({"": tree}))
    self.assertIsNotNone(ty_a.cls)
    ty_b = pytd.ClassType("B")
    ty_b.Visit(visitors.FillInLocalPointers({"": tree}))
    self.assertIsNone(ty_b.cls)

  def testFillInFunctionTypePointers(self):
    src = textwrap.dedent("def f(): ...")
    tree = self.Parse(src)
    ty = pytd.FunctionType("f", None)
    ty.Visit(visitors.FillInLocalPointers({"": tree}))
    self.assertEqual(ty.function, tree.Lookup("f"))

  def testDefaceUnresolved(self):
    builtins = self.Parse(textwrap.dedent("""
      class int(object):
        pass
    """))
    src = textwrap.dedent("""
        class A(X):
            def a(self, a: A, b: X, c: int) -> X:
                raise X()
            def b(self) -> X[int]
    """)
    expected = textwrap.dedent("""
        class A(?):
            def a(self, a: A, b: ?, c: int) -> ?:
                raise ?
            def b(self) -> ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    new_tree.Visit(visitors.VerifyVisitor())
    self.AssertSourceEquals(new_tree, expected)

  def testDefaceUnresolved2(self):
    builtins = self.Parse(textwrap.dedent("""
      from typing import Generic, TypeVar
      class int(object):
        pass
      T = TypeVar("T")
      class list(Generic[T]):
        pass
    """))
    src = textwrap.dedent("""
        from typing import Union
        class A(X):
            def a(self, a: A, b: X, c: int) -> X:
                raise X()
            def c(self) -> Union[list[X], int]
    """)
    expected = textwrap.dedent("""
        from typing import Union
        class A(?):
            def a(self, a: A, b: ?, c: int) -> ?:
                raise ?
            def c(self) -> Union[list[?], int]
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    new_tree.Visit(visitors.VerifyVisitor())
    self.AssertSourceEquals(new_tree, expected)

  def testReplaceTypes(self):
    src = textwrap.dedent("""
        class A(object):
            def a(self, a: A or B) -> A or B:
                raise A()
                raise B()
    """)
    expected = textwrap.dedent("""
        class A(object):
            def a(self: A2, a: A2 or B) -> A2 or B:
                raise A2()
                raise B()
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
    from typing import TypeVar
    def f() -> ?:
      raise MemoryError()
      raise IOError()
    def f(x: list[a]) -> ?
    def f(x: list[b or c]) -> ?
    def f(x: list[tuple[d]]) -> ?
    A = TypeVar("A")
    C = TypeVar("C")
    B = TypeVar("B")
    D = TypeVar("D")
    def f(d: A, c: B, b: C, a: D) -> ?
    """)
    src2 = textwrap.dedent("""
    def f() -> ?:
      raise IOError()
      raise MemoryError()
    def f(x: list[tuple[d]]) -> ?
    def f(x: list[a]) -> ?
    def f(x: list[b or c]) -> ?
    A = TypeVar("A")
    C = TypeVar("C")
    B = TypeVar("B")
    D = TypeVar("D")
    def f(d: A, c: B, b: C, a: D) -> ?
    """)
    tree1 = self.Parse(src1)
    tree1 = tree1.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    tree2 = self.Parse(src2)
    tree2 = tree2.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    self.AssertSourceEquals(tree1, tree2)
    self.assertEqual(tree1.Lookup("f").signatures[0].template,
                     tree2.Lookup("f").signatures[0].template)

  def testInPlaceLookupExternalClasses(self):
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
    ast1 = self.Parse(src1, name="foo")
    ast2 = self.Parse(src2, name="bar")
    ast1 = ast1.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2)))
    ast2 = ast2.Visit(visitors.LookupExternalTypes(dict(foo=ast1, bar=ast2)))
    f1, = ast1.Lookup("foo.f1").signatures
    f2, = ast2.Lookup("bar.f2").signatures
    self.assertIs(ast2.Lookup("bar.Bar"), f1.return_type.cls)
    self.assertIs(ast1.Lookup("foo.Foo"), f2.return_type.cls)

  def testLookupConstant(self):
    src1 = textwrap.dedent("""
      Foo = ...  # type: type
    """)
    src2 = textwrap.dedent("""
      class Bar(object):
        bar = ...  # type: foo.Foo
    """)
    ast1 = self.Parse(src1, name="foo")
    ast2 = self.Parse(src2, name="bar")
    ast2 = ast2.Visit(visitors.LookupExternalTypes({"foo": ast1, "bar": ast2}))
    self.assertEqual(ast2.Lookup("bar.Bar").constants[0],
                     pytd.Constant(name="bar", type=pytd.AnythingType()))

  def testLookupStarAlias(self):
    src1 = textwrap.dedent("""
      x = ...  # type: int
      T = TypeVar("T")
      class A(object): ...
      def f(x: T) -> T: ...
      B = A
    """)
    src2 = "from foo import *"
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertEqual("bar", ast2.name)
    self.assertSetEqual({a.name for a in ast2.aliases},
                        {"bar.x", "bar.T", "bar.A", "bar.f", "bar.B"})

  def testLookupStarAliasInUnnamedModule(self):
    src1 = textwrap.dedent("""
      class A(object): ...
    """)
    src2 = "from foo import *"
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2)
    name = ast2.name
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1}, self_name=None))
    self.assertEqual(name, ast2.name)
    self.assertMultiLineEqual(pytd.Print(ast2), textwrap.dedent("""\
      import foo

      A = foo.A"""))

  def testLookupTwoStarAliases(self):
    src1 = "class A(object): ..."
    src2 = "class B(object): ..."
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    ast3 = ast3.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))
    self.assertSetEqual({a.name for a in ast3.aliases}, {"baz.A", "baz.B"})

  def testLookupTwoStarAliasesWithSameClass(self):
    src1 = "class A(object): ..."
    src2 = "class A(object): ..."
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    self.assertRaises(KeyError, ast3.Visit, visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))

  def testLookupStarAliasWithDuplicateClass(self):
    src1 = "class A(object): ..."
    src2 = textwrap.dedent("""
      from foo import *
      class A(object):
        x = ...  # type: int
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd.Print(ast2), textwrap.dedent("""\
      class bar.A(object):
          x = ...  # type: int
    """))

  def testLookupTwoStarAliasesWithDefaultPyi(self):
    src1 = "def __getattr__(name) -> ?"
    src2 = "def __getattr__(name) -> ?"
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    ast3 = ast3.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))
    self.assertMultiLineEqual(pytd.Print(ast3), textwrap.dedent("""\
      from typing import Any

      def baz.__getattr__(name) -> Any: ..."""))

  def testLookupStarAliasWithDuplicateGetAttr(self):
    src1 = "def __getattr__(name) -> ?"
    src2 = textwrap.dedent("""
      from foo import *
      def __getattr__(name) -> ?
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd.Print(ast2), textwrap.dedent("""\
      from typing import Any

      def bar.__getattr__(name) -> Any: ..."""))

  def testLookupTwoStarAliasesWithDifferentGetAttrs(self):
    src1 = "def __getattr__(name) -> int"
    src2 = "def __getattr__(name) -> str"
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    self.assertRaises(KeyError, ast3.Visit, visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))

  def testLookupStarAliasWithDifferentGetAttr(self):
    src1 = "def __getattr__(name) -> int"
    src2 = textwrap.dedent("""
      from foo import *
      def __getattr__(name) -> str
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd.Print(ast2), textwrap.dedent("""\
      def bar.__getattr__(name) -> str: ..."""))

  def testCollectDependencies(self):
    src = textwrap.dedent("""
      l = ... # type: list[int or baz.BigInt]
      def f1() -> bar.Bar
      def f2() -> foo.bar.Baz
    """)
    deps = visitors.CollectDependencies()
    self.Parse(src).Visit(deps)
    self.assertSetEqual({"baz", "bar", "foo.bar"}, deps.modules)

  def testCollectDependenciesOnFunctionType(self):
    other = self.Parse("""
      def f(): ...
    """)
    ast = pytd.FunctionType("foo.bar", other.Lookup("f"))
    deps = visitors.CollectDependencies()
    ast.Visit(deps)
    self.assertSetEqual({"foo"}, deps.modules)

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
    src = textwrap.dedent("""
      from typing import List, Tuple, Union
      def f(x: Union[int, slice]) -> List[?]: ...
      def g(x: foo.C.C2) -> None: ...
    """)
    expected = textwrap.dedent("""\
      import foo.C
      from typing import Any, List, Union

      def f(x: Union[int, slice]) -> List[Any]: ...
      def g(x: foo.C.C2) -> None: ...""")
    tree = self.Parse(src)
    res = pytd.Print(tree)
    self.AssertSourceEquals(res, src)
    self.assertMultiLineEqual(res, expected)

  def testPrintImportsNamedType(self):
    # Can't get tree by parsing so build explicitly
    node = pytd.Constant("x", pytd.NamedType("typing.List"))
    tree = pytd_utils.CreateModule(name=None, constants=(node,))
    expected_src = textwrap.dedent("""
      from typing import List

      x = ...  # type: List
    """).strip()
    res = pytd.Print(tree)
    self.assertMultiLineEqual(res, expected_src)

  def testPrintImportsIgnoresExisting(self):
    src = "from foo import b"

    tree = self.Parse(src)
    res = pytd.Print(tree)
    self.assertMultiLineEqual(res, src)

  def testPrintUnionNameConflict(self):
    src = textwrap.dedent("""
      class Union: ...
      def g(x: Union) -> int or float: ...
    """)
    tree = self.Parse(src)
    res = pytd.Print(tree)
    self.AssertSourceEquals(res, src)

  def testAdjustTypeParameters(self):
    ast = self.Parse("""
      T = TypeVar("T")
      T2 = TypeVar("T2")
      def f(x: T) -> T
      class A(Generic[T]):
        def a(self, x: T2) -> None:
          self = A[T or T2]
    """)

    f = ast.Lookup("f")
    sig, = f.signatures
    p_x, = sig.params
    self.assertEqual(sig.template,
                     (pytd.TemplateItem(pytd.TypeParameter("T", scope="f")),))
    self.assertEqual(p_x.type, pytd.TypeParameter("T", scope="f"))

    cls = ast.Lookup("A")
    f_cls, = cls.methods
    sig_cls, = f_cls.signatures
    p_self, p_x_cls = sig_cls.params
    self.assertEqual(cls.template,
                     (pytd.TemplateItem(pytd.TypeParameter("T", scope="A")),))
    self.assertEqual(sig_cls.template, (pytd.TemplateItem(
        pytd.TypeParameter("T2", scope="A.a")),))
    self.assertEqual(p_self.type.parameters,
                     (pytd.TypeParameter("T", scope="A"),))
    self.assertEqual(p_x_cls.type, pytd.TypeParameter("T2", scope="A.a"))

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
    self.assertEqual((pytd.ClassType("int"),), foo_parent.parameters)
    self.assertEqual((), foo.template)
    self.assertEqual(
        (pytd.TypeParameter("T", scope="Bar"), pytd.ClassType("int")),
        bar_parent.parameters)
    self.assertEqual(
        (pytd.TemplateItem(pytd.TypeParameter("T", scope="Bar")),),
        bar.template)
    self.assertEqual((pytd.ClassType("str"), pytd.ClassType("int")),
                     qux_parent.parameters)
    self.assertEqual((), qux.template)

  def testAdjustTypeParametersWithDuplicates(self):
    ast = self.ParseWithBuiltins("""
      T = TypeVar("T")
      class A(Dict[T, T], Generic[T]): pass
    """)
    a = ast.Lookup("A")
    self.assertEqual(
        (pytd.TemplateItem(pytd.TypeParameter("T", (), None, "A")),
         pytd.TemplateItem(pytd.TypeParameter("T", (), None, "A"))),
        a.template)

  def testAdjustTypeParametersWithDuplicatesInGeneric(self):
    src = textwrap.dedent("""
      T = TypeVar("T")
      class A(Generic[T, T]): pass
    """)
    self.assertRaises(visitors.ContainerError, lambda: self.Parse(src))

  def testVerifyContainers(self):
    ast1 = self.ParseWithBuiltins("""
      from typing import SupportsInt, TypeVar
      T = TypeVar("T")
      class Foo(SupportsInt[T]): pass
    """)
    ast2 = self.ParseWithBuiltins("""
      from typing import SupportsInt
      class Foo(SupportsInt[int]): pass
    """)
    ast3 = self.ParseWithBuiltins("""
      from typing import Generic
      class Foo(Generic[int]): pass
    """)
    ast4 = self.ParseWithBuiltins("""
      from typing import List
      class Foo(List[int, str]): pass
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast1.Visit(visitors.VerifyContainers()))
    self.assertRaises(visitors.ContainerError,
                      lambda: ast2.Visit(visitors.VerifyContainers()))
    self.assertRaises(visitors.ContainerError,
                      lambda: ast3.Visit(visitors.VerifyContainers()))
    self.assertRaises(visitors.ContainerError,
                      lambda: ast4.Visit(visitors.VerifyContainers()))

  def testClearClassPointers(self):
    cls = pytd.Class("foo", None, (), (), (), None, ())
    t = pytd.ClassType("foo", cls)
    t = t.Visit(visitors.ClearClassPointers())
    self.assertIsNone(t.cls)

  def testExpandCompatibleBuiltins(self):
    src = textwrap.dedent("""
        from typing import Tuple, Union
        def f1(a: float) -> None: ...
        def f2() -> float: ...

        def f3(a: bool) -> None: ...
        def f4() -> bool: ...

        def f5(a: Union[bool, int]) -> None: ...
        def f6(a: Tuple[bool, int]) -> None: ...
    """)
    expected = textwrap.dedent("""
        from typing import Tuple, Union
        def f1(a: Union[float, int]) -> None: ...
        def f2() -> float: ...

        def f3(a: Union[bool, None]) -> None: ...
        def f4() -> bool: ...

        def f5(a: Union[bool, None, int]) -> None: ...
        def f6(a: Tuple[Union[bool, None], int]) -> None: ...
    """)

    src_tree, expected_tree = (
        self.Parse(s).Visit(visitors.LookupBuiltins(self.loader.builtins))
        for s in (src, expected))
    new_tree = src_tree.Visit(visitors.ExpandCompatibleBuiltins(
        self.loader.builtins))
    self.AssertSourceEquals(new_tree, expected_tree)

  def testAddNamePrefix(self):
    src = textwrap.dedent("""
      from typing import TypeVar
      def f(a: T) -> T: ...
      T = TypeVar("T")
      class X(Generic[T]):
        pass
    """)
    tree = self.Parse(src)
    self.assertIsNone(tree.Lookup("T").scope)
    self.assertEqual("X",
                     tree.Lookup("X").template[0].type_param.scope)
    tree = tree.Replace(name="foo").Visit(visitors.AddNamePrefix())
    self.assertIsNotNone(tree.Lookup("foo.f"))
    self.assertIsNotNone(tree.Lookup("foo.X"))
    self.assertEqual("foo", tree.Lookup("foo.T").scope)
    self.assertEqual("foo.X",
                     tree.Lookup("foo.X").template[0].type_param.scope)

  def testAddNamePrefixTwice(self):
    src = textwrap.dedent("""
      from typing import TypeVar
      x = ...  # type: ?
      T = TypeVar("T")
      class X(Generic[T]): ...
    """)
    tree = self.Parse(src)
    tree = tree.Replace(name="foo").Visit(visitors.AddNamePrefix())
    tree = tree.Replace(name="foo").Visit(visitors.AddNamePrefix())
    self.assertIsNotNone(tree.Lookup("foo.foo.x"))
    self.assertEqual("foo.foo", tree.Lookup("foo.foo.T").scope)
    self.assertEqual("foo.foo.X",
                     tree.Lookup("foo.foo.X").template[0].type_param.scope)

  def testAddNamePrefixOnClassType(self):
    src = textwrap.dedent("""
        x = ...  # type: y
        class Y: ...
    """)
    tree = self.Parse(src)
    x = tree.Lookup("x")
    x = x.Replace(type=pytd.ClassType("Y"))
    tree = tree.Replace(constants=(x,), name="foo")
    tree = tree.Visit(visitors.AddNamePrefix())
    self.assertEqual("foo.Y", tree.Lookup("foo.x").type.name)

  def testPrintMergeTypes(self):
    src = textwrap.dedent("""
      from typing import Union
      def a(a: float) -> int: ...
      def b(a: Union[int, float]) -> int: ...
      def c(a: object) -> Union[float, int]: ...
      def d(a: float) -> int: ...
      def e(a: Union[bool, None]) -> Union[bool, None]: ...
    """)
    expected = textwrap.dedent("""
      from typing import Optional, Union

      def a(a: float) -> int: ...
      def b(a: float) -> int: ...
      def c(a: object) -> Union[float, int]: ...
      def d(a: float) -> int: ...
      def e(a: bool) -> Optional[bool]: ...
    """)
    self.assertMultiLineEqual(expected.strip(),
                              pytd.Print(self.ToAST(src)).strip())

  def testPrintHeterogeneousTuple(self):
    t = pytd.TupleType(pytd.NamedType("tuple"),
                       (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertEqual("Tuple[str, float]", pytd.Print(t))

  def testVerifyHeterogeneousTuple(self):
    # Error: does not inherit from Generic
    base = pytd.ClassType("tuple")
    base.cls = pytd.Class("tuple", None, (), (), (), None, ())
    t1 = pytd.TupleType(base, (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertRaises(visitors.ContainerError,
                      lambda: t1.Visit(visitors.VerifyContainers()))
    # Error: Generic[str, float]
    gen = pytd.ClassType("typing.Generic")
    gen.cls = pytd.Class("typing.Generic", None, (), (), (), None, ())
    t2 = pytd.TupleType(gen, (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertRaises(visitors.ContainerError,
                      lambda: t2.Visit(visitors.VerifyContainers()))
    # Okay
    param = pytd.TypeParameter("T")
    parent = pytd.GenericType(gen, (param,))
    base.cls = pytd.Class(
        "tuple", None, (parent,), (), (), None, (pytd.TemplateItem(param),))
    t3 = pytd.TupleType(base, (pytd.NamedType("str"), pytd.NamedType("float")))
    t3.Visit(visitors.VerifyContainers())

  def testTypeVarValueConflict(self):
    # Conflicting values for _T.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[int], List[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def testTypeVarValueConflictHidden(self):
    # Conflicting value for _T hidden in MRO.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[int]): ...
      class B(A, List[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def testTypeVarValueConflictRelatedContainers(self):
    # List inherits from Sequence, so they share a type parameter.
    ast = self.ParseWithBuiltins("""
      from typing import List, Sequence
      class A(List[int], Sequence[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def testTypeVarValueNoConflict(self):
    # Not an error if the containers are unrelated, even if they use the same
    # type parameter name.
    ast = self.ParseWithBuiltins("""
      from typing import ContextManager, SupportsAbs
      class Foo(SupportsAbs[float], ContextManager[Foo]): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def testTypeVarValueNoConflictAmbiguousAlias(self):
    # No conflict due to T1 being aliased to two different type parameters.
    ast = self.ParseWithBuiltins("""
      from typing import Generic, TypeVar
      T1 = TypeVar("T1")
      T2 = TypeVar("T2")
      T3 = TypeVar("T3")
      T4 = TypeVar("T4")
      T5 = TypeVar("T5")
      class A(Generic[T1]): ...
      class B1(A[T2]): ...
      class B2(A[T3]): ...
      class C(B1[T4], B2[T5]): ...
      class D(C[int, str], A[str]): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def testTypeVarValueAndAliasConflict(self):
    ast = self.ParseWithBuiltins("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class A(Generic[T]): ...
      class B(A[int], A[T]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def testTypeVarAliasAndValueConflict(self):
    ast = self.ParseWithBuiltins("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class A(Generic[T]): ...
      class B(A[T], A[int]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def testVerifyContainerWithMROError(self):
    # Make sure we don't crash.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[str]): ...
      class B(List[str], A): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def testAliasPrinting(self):
    a = pytd.Alias("MyList", pytd.GenericType(
        pytd.NamedType("typing.List"), (pytd.AnythingType(),)))
    ty = pytd_utils.CreateModule("test", aliases=(a,))
    expected = textwrap.dedent("""
      from typing import Any, List

      MyList = List[Any]""")
    self.assertMultiLineEqual(expected.strip(), pytd.Print(ty).strip())

  def testPrintNoneUnion(self):
    src = textwrap.dedent("""
      from typing import Union
      def f(x: Union[str, None]) -> None: ...
      def g(x: Union[str, int, None]) -> None: ...
      def h(x: Union[None]) -> None: ...
    """)
    expected = textwrap.dedent("""
      from typing import Optional, Union

      def f(x: Optional[str]) -> None: ...
      def g(x: Optional[Union[str, int]]) -> None: ...
      def h(x: None) -> None: ...
    """)
    self.assertMultiLineEqual(expected.strip(),
                              pytd.Print(self.ToAST(src)).strip())

  def testLookupTypingClass(self):
    node = visitors.LookupClasses(pytd.NamedType("typing.Sequence"),
                                  self.loader.concat_all())
    assert node.cls

  def testCreateTypeParametersFromUnknowns(self):
    src = textwrap.dedent("""
      from typing import Dict
      def f(x: `~unknown1`) -> `~unknown1`: ...
      def g(x: `~unknown2`, y: `~unknown2`) -> None: ...
      def h(x: `~unknown3`) -> None: ...
      def i(x: Dict[`~unknown4`, `~unknown4`]) -> None: ...

      # Should not be changed
      class `~unknown5`(object):
        def __add__(self, x: `~unknown6`) -> `~unknown6`: ...
      def `~f`(x: `~unknown7`) -> `~unknown7`: ...
    """)
    expected = textwrap.dedent("""
      from typing import Dict

      _T0 = TypeVar('_T0')

      def f(x: _T0) -> _T0: ...
      def g(x: _T0, y: _T0) -> None: ...
      def h(x: `~unknown3`) -> None: ...
      def i(x: Dict[_T0, _T0]) -> None: ...

      class `~unknown5`(object):
        def __add__(self, x: `~unknown6`) -> `~unknown6`: ...
      def `~f`(x: `~unknown7`) -> `~unknown7`: ...
    """)
    ast1 = self.Parse(src)
    ast1 = ast1.Visit(visitors.CreateTypeParametersForSignatures())
    self.AssertSourceEquals(ast1, expected)

  def testRedefineTypeVar(self):
    src = textwrap.dedent("""
      def f(x: `~unknown1`) -> `~unknown1`: ...
      class `TypeVar`(object): ...
    """)
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd.Print(ast), textwrap.dedent("""\
      import typing

      _T0 = TypeVar('_T0')

      class `TypeVar`(object):
          pass


      def f(x: _T0) -> _T0: ..."""))

  def testCreateTypeParametersForNew(self):
    src = textwrap.dedent("""
      class Foo:
          def __new__(cls: Type[Foo]) -> Foo
      class Bar:
          def __new__(cls: Type[Bar], x, y, z) -> Bar
    """)
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd.Print(ast), textwrap.dedent("""\
      from typing import TypeVar

      _TBar = TypeVar('_TBar', bound=Bar)
      _TFoo = TypeVar('_TFoo', bound=Foo)

      class Foo:
          def __new__(cls: Type[_TFoo]) -> _TFoo: ...

      class Bar:
          def __new__(cls: Type[_TBar], x, y, z) -> _TBar: ...
    """))

  def testKeepCustomNew(self):
    src = textwrap.dedent("""\
      class Foo:
          def __new__(cls: Type[X]) -> X: ...

      class Bar:
          def __new__(cls, x: Type[Bar]) -> Bar: ...
    """)
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd.Print(ast), src)

  def testPrintTypeParameterBound(self):
    src = textwrap.dedent("""
      from typing import TypeVar
      T = TypeVar("T", bound=str)
    """)
    self.assertMultiLineEqual(pytd.Print(self.Parse(src)), textwrap.dedent("""\
      from typing import TypeVar

      T = TypeVar('T', bound=str)"""))

  def testPrintCls(self):
    src = textwrap.dedent("""
      class A(object):
          def __new__(cls: Type[A]) -> A: ...
    """)
    self.assertMultiLineEqual(pytd.Print(self.Parse(src)), textwrap.dedent("""\
      class A(object):
          def __new__(cls) -> A: ...
    """))

  def testPrintNoReturn(self):
    src = textwrap.dedent("""
      def f() -> nothing
    """)
    self.assertMultiLineEqual(pytd.Print(self.Parse(src)), textwrap.dedent("""\
      from typing import NoReturn

      def f() -> NoReturn: ..."""))

  def testPrintMultilineSignature(self):
    src = textwrap.dedent("""
      def f(x: int, y: str, z: bool) -> list[str]:
        pass
    """)
    self.assertMultiLineEqual(
        pytd.Print(self.Parse(src), multiline_args=True),
        textwrap.dedent("""\
           from typing import List

           def f(
               x: int,
               y: str,
               z: bool
           ) -> List[str]: ..."""))

  def testRenameBuiltinsPrefix(self):
    """builtins.foo should get rewritten to __builtin__.foo and then to foo."""
    src = textwrap.dedent("""
      import builtins
      class MyError(builtins.KeyError): ...
    """)
    self.assertMultiLineEqual(pytd.Print(self.Parse(src)), textwrap.dedent("""\
      class MyError(KeyError):
          pass
    """))

  def testQualifyRelativeNames(self):
    src = "from . import foo"
    ast = self.Parse(src).Visit(visitors.QualifyRelativeNames("package"))
    _, module = ast.Lookup("foo")  # Alias(foo, Module)
    self.assertEqual(module.module_name, "package.foo")


class TestAncestorMap(unittest.TestCase):

  def testGetAncestorMap(self):
    ancestors = visitors._GetAncestorMap()
    # TypeDeclUnit is the top of the food chain - no ancestors other than
    # itself.
    self.assertEqual({"TypeDeclUnit"}, ancestors["TypeDeclUnit"])
    # NamedType can appear in quite a few places, spot check a few.
    named_type = ancestors["NamedType"]
    self.assertIn("TypeDeclUnit", named_type)
    self.assertIn("Parameter", named_type)
    self.assertIn("GenericType", named_type)
    self.assertIn("NamedType", named_type)
    # Check a few places where NamedType cannot appear.
    self.assertNotIn("ClassType", named_type)
    self.assertNotIn("NothingType", named_type)
    self.assertNotIn("AnythingType", named_type)


class ReplaceWithAnyReferenceVisitorTest(unittest.TestCase):

  def testAnyReplacement(self):
    class_type_match = pytd.ClassType("match.foo")
    named_type_match = pytd.NamedType("match.bar")
    class_type_no_match = pytd.ClassType("no.match.foo")
    named_type_no_match = pytd.NamedType("no.match.bar")
    generic_type_match = pytd.GenericType(class_type_match, ())
    generic_type_no_match = pytd.GenericType(class_type_no_match, ())

    visitor = visitors.ReplaceWithAnyReferenceVisitor("match.")
    self.assertEqual(class_type_no_match, class_type_no_match.Visit(visitor))
    self.assertEqual(named_type_no_match, named_type_no_match.Visit(visitor))
    self.assertEqual(generic_type_no_match,
                     generic_type_no_match.Visit(visitor))
    self.assertEqual(pytd.AnythingType,
                     class_type_match.Visit(visitor).__class__)
    self.assertEqual(pytd.AnythingType,
                     named_type_match.Visit(visitor).__class__)
    self.assertEqual(pytd.AnythingType,
                     generic_type_match.Visit(visitor).__class__)


if __name__ == "__main__":
  unittest.main()
