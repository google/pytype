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
import unittest
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser_test
from pytype.pytd.parse import visitors
import unittest


class TestOptimize(parser_test.ParserTest):
  """Test the visitors in optimize.py."""

  def OptimizedString(self, data):
    tree = self.Parse(data)
    new_tree = optimize.Optimize(tree)
    return pytd.Print(new_tree)

  def AssertOptimizeEquals(self, src, new_src):
    self.AssertSourceEquals(self.OptimizedString(src), new_src)

  def testOneFunction(self):
    src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int raises AssertionError, ValueError
    """)
    self.AssertOptimizeEquals(src, src)

  def testFunctionDuplicate(self):
    src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int raises AssertionError, ValueError
        def foo(a: int, c: bool) -> int raises AssertionError, ValueError
    """)
    new_src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int raises AssertionError, ValueError
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testComplexFunctionDuplicate(self):
    src = textwrap.dedent("""
        def foo(a: int or float, c: bool) -> list[int] raises IndexError
        def foo(a: str, c: str) -> str
        def foo(a: int, ...) -> int or float raises list[str]
        def foo(a: int or float, c: bool) -> list[int] raises IndexError
        def foo(a: int, ...) -> int or float raises list[str]
    """)
    new_src = textwrap.dedent("""
        def foo(a: int or float, c: bool) -> list[int] raises IndexError
        def foo(a: str, c: str) -> str
        def foo(a: int, ...) -> int or float raises list[str]
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testCombineReturns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: int) -> float
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testCombineRedundantReturns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: int) -> float
        def foo(a: int) -> int or float
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testCombineUnionReturns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int or float
        def bar(a: str) -> str
        def foo(a: int) -> str or unicode
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float or str or unicode
        def bar(a: str) -> str
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testCombineExceptions(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int raises ValueError
        def foo(a: int) -> int raises IndexError
        def foo(a: float) -> int raises IndexError
        def foo(a: int) -> int raises AttributeError
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int raises ValueError, IndexError, AttributeError
        def foo(a: float) -> int raises IndexError
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testMixedCombine(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int raises ValueError
        def foo(a: int) -> float raises ValueError
        def foo(a: int) -> int raises IndexError
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float raises ValueError, IndexError
    """)
    self.AssertOptimizeEquals(src, new_src)

  def testLossy(self):
    # Lossy compression is hard to test, since we don't know to which degree
    # "compressible" items will be compressed. This test only checks that
    # non-compressible things stay the same.
    src = textwrap.dedent("""
        def foo(a: int) -> float raises IndexError
        def foo(a: str) -> complex raises AssertionError
    """)
    optimized = optimize.Optimize(self.Parse(src),
                                  lossy=True, use_abcs=False)
    self.AssertSourceEquals(optimized, src)

  @unittest.skip("Needs ABCs to be included in the builtins")
  def testABCs(self):
    src = textwrap.dedent("""
        def foo(a: int or float) -> NoneType
        def foo(a: int or complex or float) -> NoneType
    """)
    new_src = textwrap.dedent("""
        def foo(a: Real) -> NoneType
        def foo(a: Complex) -> NoneType
    """)
    optimized = optimize.Optimize(self.Parse(src),
                                  lossy=True, use_abcs=True)
    self.AssertSourceEquals(optimized, new_src)

  def testDuplicatesInUnions(self):
    src = textwrap.dedent("""
      def a(x: int or float or complex) -> bool
      def b(x: int or float) -> bool
      def c(x: int or int or int) -> bool
      def d(x: int or int) -> bool
      def e(x: float or int or int or float) -> bool
      def f(x: float or int) -> bool
    """)
    new_src = textwrap.dedent("""
      def a(x) -> bool  # max_union=2 makes this object
      def b(x: int or float) -> bool
      def c(x: int) -> bool
      def d(x: int) -> bool
      def e(x: float or int) -> bool
      def f(x: float or int) -> bool
    """)
    optimized = optimize.Optimize(self.Parse(src),
                                  lossy=False, max_union=2)
    self.AssertSourceEquals(optimized, new_src)

  def testSimplifyUnions(self):
    src = textwrap.dedent("""
      a = ...  # type: int or int
      b = ...  # type: int or ?
      c = ...  # type: int or (int or float)
    """)
    new_src = textwrap.dedent("""
      a = ...  # type: int
      b = ...  # type: ?
      c = ...  # type: int or float
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.SimplifyUnions()),
        new_src)

  def testExpand(self):
    src = textwrap.dedent("""
        def foo(a: int or float, z: complex or str, u: bool) -> file
    """)
    new_src = textwrap.dedent("""
        def foo(a: int, z: complex, u: bool) -> file
        def foo(a: int, z: str, u: bool) -> file
        def foo(a: float, z: complex, u: bool) -> file
        def foo(a: float, z: str, u: bool) -> file
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.ExpandSignatures()),
        new_src)

  def testFactorize(self):
    src = textwrap.dedent("""
        def foo(a: int) -> file
        def foo(a: int, x: complex) -> file
        def foo(a: int, x: str) -> file
        def foo(a: float, x: complex) -> file
        def foo(a: float, x: str) -> file
        def foo(a: int, x: file, ...) -> file
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> file
        def foo(a: int or float, x: complex or str) -> file
        def foo(a: int, x: file, ...) -> file
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.Factorize()), new_src)

  def testFactorizeMutable(self):
    src = textwrap.dedent("""
        def foo(a: list[bool], b: X) -> file:
            a := list[int]
        def foo(a: list[bool], b: Y) -> file:
            a := list[int]
        # not groupable:
        def bar(a: int, b: list[int]) -> file:
            b := list[complex]
        def bar(a: int, b: list[float]) -> file:
            b := list[str]
    """)
    new_src = textwrap.dedent("""
        def foo(a: list[bool], b: X or Y) -> file:
            a := list[int]
        def bar(a: int, b: list[int]) -> file:
            b := list[complex]
        def bar(a: int, b: list[float]) -> file:
            b := list[str]
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.Factorize()), new_src)

  def testOptionalArguments(self):
    src = textwrap.dedent("""
        def foo(a: A, ...) -> Z
        def foo(a: A) -> Z
        def foo(a: A, b: B) -> Z
        def foo(a: A, b: B, ...) -> Z
        def foo() -> Z
    """)
    expected = textwrap.dedent("""
        def foo(a: A, ...) -> Z
        def foo() -> Z
    """)
    new_src = self.ApplyVisitorToString(src, optimize.ApplyOptionalArguments())
    self.AssertSourceEquals(new_src, expected)

  def testABCSuperClasses(self):
    src = textwrap.dedent("""
        def f(x: list or tuple, y: frozenset or set) -> int or float
        def g(x: dict or Mapping, y: complex or int) -> set or dict or tuple or Container
        def h(x) -> ?
    """)
    expected = textwrap.dedent("""
        def f(x: Sequence, y: Set) -> Real
        def g(x: Mapping, y: Complex) -> Container
        def h(x) -> ?
    """)
    visitor = optimize.FindCommonSuperClasses(use_abcs=True)
    new_src = self.ApplyVisitorToString(src, visitor)
    self.AssertSourceEquals(new_src, expected)

  def testBuiltinSuperClasses(self):
    src = textwrap.dedent("""
        def f(x: list or object, y: int or float) -> int or bool
    """)
    expected = textwrap.dedent("""
        def f(x, y) -> int
    """)
    visitor = optimize.FindCommonSuperClasses(use_abcs=False)
    new_src = self.ApplyVisitorToString(src, visitor)
    self.AssertSourceEquals(new_src, expected)

  def testUserSuperClassHierarchy(self):
    class_data = textwrap.dedent("""
        class AB(object):
            pass

        class EFG(object):
            pass

        class A(AB, EFG):
            pass

        class B(AB):
            pass

        class E(EFG, AB):
            pass

        class F(EFG):
            pass

        class G(EFG):
            pass
    """)

    src = textwrap.dedent("""
        def f(x: A or B, y: A, z: B) -> E or F or G
        def g(x: E or F or G or B) -> E or F
        def h(x) -> ?
    """) + class_data

    expected = textwrap.dedent("""
        def f(x: AB, y: A, z: B) -> EFG
        def g(x) -> EFG
        def h(x) -> ?
    """) + class_data

    hierarchy = self.Parse(src).Visit(visitors.ExtractSuperClassesByName())
    visitor = optimize.FindCommonSuperClasses(hierarchy, use_abcs=False)
    new_src = self.ApplyVisitorToString(src, visitor)
    self.AssertSourceEquals(new_src, expected)

  def testCollapseLongUnions(self):
    src = textwrap.dedent("""
        def f(x: A or B or C or D) -> X
        def g(x: A or B or C or D or E) -> X
        def h(x: A or object) -> X
    """)
    expected = textwrap.dedent("""
        def f(x: A or B or C or D) -> X
        def g(x) -> X
        def h(x) -> X
    """)
    new_src = self.ApplyVisitorToString(
        src, optimize.CollapseLongUnions(max_length=4))
    self.AssertSourceEquals(new_src, expected)

  def testCollapseLongConstantUnions(self):
    src = textwrap.dedent("""
      x = ...  # type: A or B or C or D
      y = ...  # type: A or B or C or D or E
    """)
    expected = textwrap.dedent("""
      x = ...  # type: A or B or C or D
      y = ...  # type: ?
    """)
    new_src = self.ApplyVisitorToString(
        src, optimize.CollapseLongConstantUnions(max_length=4))
    self.AssertSourceEquals(new_src, expected)

  def testCombineContainers(self):
    src = textwrap.dedent("""
        def f(x: list[int] or list[float]) -> ?
        def g(x: list[int] or str or list[float] or set[int] or long) -> ?
        def h(x: list[int] or list[str] or set[int] or set[float]) -> ?
        def i(x: list[int] or list[int]) -> ?
        def j(x: dict[int, float] or dict[float, int]) -> ?
        def k(x: dict[int, bool] or list[int] or dict[bool, int] or list[bool]) -> ?
    """)
    expected = textwrap.dedent("""
        def f(x: list[int or float]) -> ?
        def g(x: list[int or float] or str or set[int] or long) -> ?
        def h(x: list[int or str] or set[int or float]) -> ?
        def i(x: list[int]) -> ?
        def j(x: dict[int or float, float or int]) -> ?
        def k(x: dict[int or bool, bool or int] or list[int or bool]) -> ?
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def testCombineContainersMultiLevel(self):
    src = textwrap.dedent("""
      v = ...  # type: list[tuple[long or int]] or list[tuple[float or bool]]
    """)
    expected = textwrap.dedent("""
      v = ...  # type: list[tuple[long or int or float or bool]]
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def testPullInMethodClasses(self):
    src = textwrap.dedent("""
        class A(object):
            mymethod1 = ...  # type: Method1
            mymethod2 = ...  # type: Method2
            member = ...  # type: Method3
            mymethod4 = ...  # type: Method4
        class Method1(object):
            def __call__(self: A, x: int) -> ?
        class Method2(object):
            def __call__(self: ?, x: int) -> ?
        class Method3(object):
            def __call__(x: bool, y: int) -> ?
        class Method4(object):
            def __call__(self: ?) -> ?
        class B(Method4):
            pass
    """)
    expected = textwrap.dedent("""
        class A(object):
            member = ...  # type: Method3
            def mymethod1(self, x: int) -> ?
            def mymethod2(self, x: int) -> ?
            def mymethod4(self) -> ?

        class Method3(object):
            def __call__(x: bool, y: int) -> ?

        class Method4(object):
            def __call__(self) -> ?

        class B(Method4):
            pass
    """)
    new_src = self.ApplyVisitorToString(src,
                                        optimize.PullInMethodClasses())
    self.AssertSourceEquals(new_src, expected)

  def testAddInheritedMethods(self):
    src = textwrap.dedent("""
        class A():
            foo = ...  # type: bool
            def f(self, x: int) -> float
            def h(self) -> complex

        class B(A):
            bar = ...  # type: int
            def g(self, y: int) -> bool
            def h(self, z: float) -> ?
    """)
    expected = textwrap.dedent("""
        class A():
            foo = ...  # type: bool
            def f(self, x: int) -> float
            def h(self) -> complex

        class B(A):
            bar = ...  # type: int
            foo = ...  # type: bool
            def g(self, y: int) -> bool
            def h(self, z: float) -> ?
            def f(self, x: int) -> float
    """)
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, builtins.GetBuiltinsPyTD())
    ast = ast.Visit(optimize.AddInheritedMethods())
    self.AssertSourceEquals(ast, expected)

  def testRemoveInheritedMethodsWithoutSelf(self):
    src = textwrap.dedent("""
        class Bar(object):
          def baz(self) -> int

        class Foo(Bar):
          def baz(self) -> int
          def bar() -> float
    """)
    expected = textwrap.dedent("""
        class Bar(object):
          def baz(self) -> int

        class Foo(Bar):
          def bar() -> float
    """)
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, builtins.GetBuiltinsPyTD())
    ast = ast.Visit(optimize.RemoveInheritedMethods())
    self.AssertSourceEquals(ast, expected)

  def testRemoveInheritedMethods(self):
    src = textwrap.dedent("""
        class A():
            def f(self, y: int) -> bool
            def g(self) -> float

        class B(A):
            def b(self) -> B
            def f(self, y: int) -> bool

        class C(A):
            def c(self) -> C
            def f(self, y: int) -> bool

        class D(B):
            def g(self) -> float
            def d(self) -> D
    """)
    expected = textwrap.dedent("""
        class A():
            def f(self, y: int) -> bool
            def g(self) -> float

        class B(A):
            def b(self) -> B

        class C(A):
            def c(self) -> C

        class D(B):
            def d(self) -> D
    """)
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, builtins.GetBuiltinsPyTD())
    ast = ast.Visit(optimize.RemoveInheritedMethods())
    self.AssertSourceEquals(ast, expected)

  def testAbsorbMutableParameters(self):
    src = textwrap.dedent("""
        def popall(x: list[?]) -> ?:
            x := list[nothing]
        def add_float(x: list[int]) -> ?:
            x := list[int or float]
        def f(x: list[int]) -> ?:
            x := list[int or float]
    """)
    expected = textwrap.dedent("""
        def popall(x: list[?]) -> ?
        def add_float(x: list[int or float]) -> ?
        def f(x: list[int or float]) -> ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(optimize.AbsorbMutableParameters())
    new_tree = new_tree.Visit(optimize.CombineContainers())
    self.AssertSourceEquals(new_tree, expected)

  def testAbsorbMutableParametersFromMethods(self):
    # This is a test for intermediate data. See AbsorbMutableParameters class
    # pydoc about how AbsorbMutableParameters works on methods.
    src = textwrap.dedent("""
        T = TypeVar('T')
        class MyClass(Generic[T], object):
            NEW = TypeVar('NEW')
            def append(self, x: NEW) -> ?:
                self := MyClass[T or NEW]
    """)
    expected = textwrap.dedent("""
        T = TypeVar('T')
        class MyClass(Generic[T], object):
            NEW = TypeVar('NEW')
            def append(self: MyClass[T or NEW], x: NEW) -> ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(optimize.AbsorbMutableParameters())
    new_tree = new_tree.Visit(optimize.CombineContainers())
    self.AssertSourceEquals(new_tree, expected)

  def testMergeTypeParameters(self):
    # This test uses pytd of the kind that's typically the output of
    # AbsorbMutableParameters.
    # See comment in RemoveMutableParameters
    src = textwrap.dedent("""
      T = TypeVar('T')
      class A(Generic[T], object):
          T2 = TypeVar('T2')
          T3 = TypeVar('T3')
          def foo(self, x: T or T2) -> T2
          def bar(self, x: T or T2 or T3) -> T3
          def baz(self, x: T or T2, y: T2 or T3) -> ?

      K = TypeVar('K')
      V = TypeVar('V')
      class D(Generic[K, V], object):
          T = TypeVar('T')
          def foo(self, x: T) -> K or T
          def bar(self, x: T) -> V or T
          def baz(self, x: K or V) -> K or V
          def lorem(self, x: T) -> T or K or V
          def ipsum(self, x: T) -> T or K
    """)
    expected = textwrap.dedent("""
      T = TypeVar('T')
      class A(Generic[T], object):
          def foo(self, x: T) -> T
          def bar(self, x: T) -> T
          def baz(self, x: T, y: T) -> ?

      K = TypeVar('K')
      V = TypeVar('V')
      class D(Generic[K, V], object):
          def foo(self, x: K) -> K
          def bar(self, x: V) -> V
          def baz(self, x: K or V) -> K or V
          def lorem(self, x: K or V) -> K or V
          def ipsum(self, x: K) -> K
      """)
    tree = self.Parse(src)
    new_tree = tree.Visit(optimize.MergeTypeParameters())
    self.AssertSourceEquals(new_tree, expected)

if __name__ == "__main__":
  unittest.main()
