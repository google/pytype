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
from pytype.pytd.parse import parser_test
from pytype.pytd.parse import visitors
import unittest


# All of these tests implicitly test pytd.Print because
# parser_test.AssertSourceEquals() uses pytd.Print.


class TestVisitors(parser_test.ParserTest):
  """Tests the classes in parse/visitors."""

  def testLookupClasses(self):
    src = textwrap.dedent("""
        class object:
            pass

        class A:
            def a(self, a: A, b: B) -> A or B raises A, B

        class B:
            def b(self, a: A, b: B) -> A or B raises A, B
    """)
    tree = self.Parse(src)
    new_tree = visitors.LookupClasses(tree)
    self.AssertSourceEquals(new_tree, src)
    new_tree.Visit(visitors.VerifyLookup())

  def testMaybeInPlaceFillInClasses(self):
    src = textwrap.dedent("""
        class A:
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
      class int:
        pass
    """))
    src = textwrap.dedent("""
        class A(X):
            def a(self, a: A, b: X, c: int) -> X raises X
    """)
    expected = textwrap.dedent("""
        class A(?):
            def a(self, a: A, b: ?, c: int) -> ? raises ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    self.AssertSourceEquals(new_tree, expected)

  def testReplaceTypes(self):
    src = textwrap.dedent("""
        class A:
            def a(self, a: A or B) -> A or B raises A, B
    """)
    expected = textwrap.dedent("""
        class A:
            def a(self: A2, a: A2 or B) -> A2 or B raises A2, B
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.ReplaceTypes({"A": pytd.NamedType("A2")}))
    self.AssertSourceEquals(new_tree, expected)

  def testSuperClassesByName(self):
    src = textwrap.dedent("""
      class A(nothing):
          pass
      class B(nothing):
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
    self.assertItemsEqual((), data["A"])
    self.assertItemsEqual((), data["B"])
    self.assertItemsEqual(("A",), data["C"])
    self.assertItemsEqual(("A", "B"), data["D"])
    self.assertItemsEqual(("A", "C", "D"), data["E"])

  def testSuperClasses(self):
    src = textwrap.dedent("""
      class A(nothing):
          pass
      class B(nothing):
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
    self.assertItemsEqual([], [t.name for t in data[ast.Lookup("A")]])
    self.assertItemsEqual([], [t.name for t in data[ast.Lookup("B")]])
    self.assertItemsEqual(["A"], [t.name for t in data[ast.Lookup("C")]])
    self.assertItemsEqual(["A", "B"], [t.name for t in data[ast.Lookup("D")]])
    self.assertItemsEqual(["C", "D", "A"],
                          [t.name for t in data[ast.Lookup("E")]])

  def testStripSelf(self):
    src = textwrap.dedent("""
        def add(x: int, y: int) -> int
        class A:
            def bar(self, x: int) -> float
            def baz(self) -> float
            def foo(self, x: int, y: float) -> float
    """)
    expected = textwrap.dedent("""
        def add(x: int, y: int) -> int

        class A:
            def bar(x: int) -> float
            def baz() -> float
            def foo(x: int, y: float) -> float
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.StripSelf())
    self.AssertSourceEquals(new_tree, expected)

  def testRemoveUnknownClasses(self):
    src = textwrap.dedent("""
        class `~unknown1`(nothing):
            pass
        class `~unknown2`(nothing):
            pass
        class A:
            def foobar(x: `~unknown1`, y: `~unknown2`) -> `~unknown1` or int
    """)
    expected = textwrap.dedent("""
        class A:
            def foobar(x, y) -> ? or int
    """)
    tree = self.Parse(src)
    tree = tree.Visit(visitors.RemoveUnknownClasses())
    self.AssertSourceEquals(tree, expected)

  def testFindUnknownVisitor(self):
    src = textwrap.dedent("""
        class `~unknown1`(nothing):
          pass
        class `~unknown_foobar`(nothing):
          pass
        class `~int`(nothing):
          pass
        class A(nothing):
          def foobar(self, x: `~unknown1`) -> ?
        class B(nothing):
          def foobar(self, x: `~int`) -> ?
        class C(nothing):
          x: `~unknown_foobar`
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
    def f(x: list<a>) -> ?
    def f(x: list<b or c>) -> ?
    def f(x: list<tuple<d>>) -> ?
    """)
    src2 = textwrap.dedent("""
    def f() -> ? raises IOError, MemoryError
    def f(x: list<tuple<d>>) -> ?
    def f(x: list<a>) -> ?
    def f(x: list<b or c>) -> ?
    """)
    tree1 = self.Parse(src1)
    tree1 = tree1.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    tree2 = self.Parse(src2)
    tree2 = tree2.Visit(visitors.CanonicalOrderingVisitor(sort_signatures=True))
    self.AssertSourceEquals(tree1, tree2)

  def testInPlaceLookupExternalClasses(self):
    src1 = textwrap.dedent("""
      def f1() -> bar.Bar
      class Foo:
        pass
    """)
    src2 = textwrap.dedent("""
      def f2() -> foo.Foo
      class Bar:
        pass
    """)
    ast1 = self.Parse(src1)
    ast2 = self.Parse(src2)
    ast1.Visit(visitors.InPlaceLookupExternalClasses(dict(foo=ast1, bar=ast2)))
    ast2.Visit(visitors.InPlaceLookupExternalClasses(dict(foo=ast1, bar= ast2)))
    f1, = ast1.Lookup("f1").signatures
    f2, = ast2.Lookup("f2").signatures
    self.assertIs(ast2.Lookup("Bar"), f1.return_type.cls)
    self.assertIs(ast1.Lookup("Foo"), f2.return_type.cls)

  def testInPlaceLookupExternalClassesByFullName(self):
    src1 = textwrap.dedent("""
      def f1() -> bar.Bar
      class Foo:
        pass
    """)
    src2 = textwrap.dedent("""
      def f2() -> foo.Foo
      class Bar:
        pass
    """)
    ast1 = self.Parse(src1).Visit(visitors.AddNamePrefix("foo."))
    ast2 = self.Parse(src2).Visit(visitors.AddNamePrefix("bar."))
    ast1.Visit(visitors.InPlaceLookupExternalClasses(dict(foo=ast1, bar=ast2),
                                                     full_names=True))
    ast2.Visit(visitors.InPlaceLookupExternalClasses(dict(foo=ast1, bar=ast2),
                                                     full_names=True))
    f1, = ast1.Lookup("foo.f1").signatures
    f2, = ast2.Lookup("bar.f2").signatures
    self.assertIs(ast2.Lookup("bar.Bar"), f1.return_type.cls)
    self.assertIs(ast1.Lookup("foo.Foo"), f2.return_type.cls)

  def testCollectDependencies(self):
    src = textwrap.dedent("""
      l: list<int or baz.BigInt>
      def f1() -> bar.Bar
      def f2() -> foo.bar.Baz
    """)
    deps = visitors.CollectDependencies()
    self.Parse(src).Visit(deps)
    self.assertSetEqual({"baz", "bar", "foo.bar"}, deps.modules)


if __name__ == "__main__":
  unittest.main()
