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

from pytype import load_pytd
from pytype.pytd import optimize
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.pytd.parse import parser_test_base
import six
import unittest


class TestOptimize(parser_test_base.ParserTest):
  """Test the visitors in optimize.py."""

  @classmethod
  def setUpClass(cls):
    super(TestOptimize, cls).setUpClass()
    cls.loader = load_pytd.Loader(None, cls.python_version)
    cls.builtins = cls.loader.builtins
    cls.typing = cls.loader.typing

  def ParseAndResolve(self, src):
    ast = self.Parse(src)
    return ast.Visit(visitors.LookupBuiltins(self.builtins))

  def Optimize(self, ast, **kwargs):
    return optimize.Optimize(ast, self.builtins, **kwargs)

  def OptimizedString(self, data):
    tree = self.Parse(data) if isinstance(data, six.string_types) else data
    new_tree = self.Optimize(tree)
    return pytd_utils.Print(new_tree)

  def AssertOptimizeEquals(self, src, new_src):
    self.AssertSourceEquals(self.OptimizedString(src), new_src)

  def test_one_function(self):
    src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int:
          raise AssertionError()
          raise ValueError()
    """)
    self.AssertOptimizeEquals(src, src)

  def test_function_duplicate(self):
    src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int:
          raise AssertionError()
          raise ValueError()
        def foo(a: int, c: bool) -> int:
          raise AssertionError()
          raise ValueError()
    """)
    new_src = textwrap.dedent("""
        def foo(a: int, c: bool) -> int:
          raise AssertionError()
          raise ValueError()
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_complex_function_duplicate(self):
    src = textwrap.dedent("""
        def foo(a: int or float, c: bool) -> list[int]:
          raise IndexError()
        def foo(a: str, c: str) -> str
        def foo(a: int, ...) -> int or float:
          raise list[str]()
        def foo(a: int or float, c: bool) -> list[int]:
          raise IndexError()
        def foo(a: int, ...) -> int or float:
          raise list[str]()
    """)
    new_src = textwrap.dedent("""
        def foo(a: float, c: bool) -> list[int]:
          raise IndexError()
        def foo(a: str, c: str) -> str
        def foo(a: int, ...) -> int or float:
          raise list[str]()
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_remove_redundant_signature(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: int or bool) -> int
    """)
    expected = textwrap.dedent("""
        def foo(a: int or bool) -> int
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  def test_remove_redundant_signature_with_exceptions(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int:
          raise IOError()
        def foo(a: int or bool) -> int
    """)
    expected = textwrap.dedent("""
        def foo(a: int) -> int:
          raise IOError()
        def foo(a: int or bool) -> int
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  def test_remove_redundant_signature_with_subclasses(self):
    src = textwrap.dedent("""
        def foo(a: bool) -> int
        def foo(a: int) -> int
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_with_any1(self):
    src = textwrap.dedent("""
        def foo(a: ?) -> ?
        def foo(a: int) -> int
    """)
    new_src = textwrap.dedent("""
        def foo(a) -> ?
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_with_any2(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: ?) -> ?
    """)
    new_src = textwrap.dedent("""
        def foo(a) -> ?
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_with_optional1(self):
    src = textwrap.dedent("""
        def foo(a: int = ...) -> int
        def foo(a: ? = ...) -> int
    """)
    new_src = textwrap.dedent("""
        def foo(a = ...) -> int
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_with_optional2(self):
    src = textwrap.dedent("""
        def foo(a: ? = ...) -> int
        def foo(a: int = ...) -> int
    """)
    new_src = textwrap.dedent("""
        def foo(a = ...) -> int
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signatures_with_long_union(self):
    src = textwrap.dedent("""
        from typing import Union
        def foo(x: None = ...) -> None: ...
        def foo(x: Union[int, complex, float, long, set, list, unicode,
                         dict, tuple, str, module, OSError, bytearray,
                         KeyError, slice, None]) -> None: ...
    """)
    new_src = textwrap.dedent("""
        def foo(x:None = ...) -> None
        def foo(x) -> None
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_with_object(self):
    src = textwrap.dedent("""
        def foo(x) -> ?
        def foo(x: int) -> int
    """)
    new_src = textwrap.dedent("""
        def foo(x) -> ?
    """)
    ast = self.ParseAndResolve(src)
    self.AssertOptimizeEquals(ast, new_src)

  def test_remove_redundant_signature_any_type(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: ?) -> int
        def bar(a: ?) -> int
        def bar(a: int) -> int
        def baz(a: ?) -> ?
        def baz(a: int) -> int
        def two(a: ?) -> int
        def two(a: int) -> ?
    """)
    new_src = textwrap.dedent("""
        def foo(a) -> int
        def bar(a) -> int
        def baz(a) -> ?
        def two(a) -> int
        def two(a: int) -> ?
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_remove_redundant_signature_generic(self):
    src = textwrap.dedent("""
        def foo(a: list[int]) -> list[int]
        def foo(a: list) -> list
        def bar(a: list) -> list
        def bar(a: list[int]) -> list[int]
    """)
    new_src = textwrap.dedent("""
        def foo(a: list) -> list
        def bar(a: list) -> list
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_remove_redundant_signature_template(self):
    src = textwrap.dedent("""
        T = TypeVar("T")
        class A(Generic[T]):
          def foo(a: int) -> int
          def foo(a: T) -> T
          def foo(a: int or bool) -> int
    """)
    expected = textwrap.dedent("""
        T = TypeVar("T")
        class A(Generic[T]):
          def foo(a: T) -> T
          def foo(a: int or bool) -> int
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  def test_remove_redundant_signature_two_type_params(self):
    src = textwrap.dedent("""
        X = TypeVar("X")
        Y = TypeVar("Y")
        class A(Generic[X, Y]):
          def foo(a: X) -> Y
          def foo(a: Y) -> Y
    """)
    expected = textwrap.dedent("""
        X = TypeVar("X")
        Y = TypeVar("Y")
        class A(Generic[X, Y]):
          def foo(a: X) -> Y
          def foo(a: Y) -> Y
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  @unittest.skip("Not supported yet.")
  def test_remove_redundant_signature_generic_left_side(self):
    src = textwrap.dedent("""
        X = TypeVar("X")
        def foo(a: X, b: int) -> X
        def foo(a: X, b: ?) -> X
    """)
    expected = textwrap.dedent("""
        X = TypeVar("X")
        def foo(a: X, b: ?) -> X
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  def test_remove_redundant_signature_polymorphic(self):
    src = textwrap.dedent("""
        T = TypeVar("T")
        def foo(a: T) -> T
        def foo(a: int or bool) -> int
    """)
    expected = textwrap.dedent("""
        T = TypeVar("T")
        def foo(a: T) -> T
    """)
    ast = self.Parse(src)
    ast = ast.Visit(optimize.RemoveRedundantSignatures(
        optimize.SuperClassHierarchy({})))
    self.AssertSourceEquals(ast, expected)

  def test_combine_returns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: int) -> float
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_combine_redundant_returns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int
        def foo(a: int) -> float
        def foo(a: int) -> int or float
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_combine_union_returns(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int or float
        def bar(a: str) -> str
        def foo(a: int) -> str or bytes
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float or str or bytes
        def bar(a: str) -> str
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_combine_exceptions(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int:
          raise ValueError()
        def foo(a: int) -> int:
          raise IndexError()
        def foo(a: float) -> int:
          raise IndexError()
        def foo(a: int) -> int:
          raise AttributeError()
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int:
          raise ValueError()
          raise IndexError()
          raise AttributeError()
        def foo(a: float) -> int:
          raise IndexError()
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_mixed_combine(self):
    src = textwrap.dedent("""
        def foo(a: int) -> int:
          raise ValueError()
        def foo(a: int) -> float:
          raise ValueError()
        def foo(a: int) -> int:
          raise IndexError()
    """)
    new_src = textwrap.dedent("""
        def foo(a: int) -> int or float:
          raise ValueError()
          raise IndexError()
    """)
    self.AssertOptimizeEquals(src, new_src)

  def test_lossy(self):
    # Lossy compression is hard to test, since we don't know to which degree
    # "compressible" items will be compressed. This test only checks that
    # non-compressible things stay the same.
    src = textwrap.dedent("""
        def foo(a: int) -> float:
          raise IndexError()
        def foo(a: str) -> complex:
          raise AssertionError()
    """)
    optimized = self.Optimize(self.Parse(src), lossy=True, use_abcs=False)
    self.AssertSourceEquals(optimized, src)

  @unittest.skip("Needs ABCs to be included in the builtins")
  def test_abcs(self):
    src = textwrap.dedent("""
        def foo(a: int or float) -> NoneType
        def foo(a: int or complex or float) -> NoneType
    """)
    new_src = textwrap.dedent("""
        def foo(a: Real) -> NoneType
        def foo(a: Complex) -> NoneType
    """)
    optimized = self.Optimize(self.Parse(src), lossy=True, use_abcs=True)
    self.AssertSourceEquals(optimized, new_src)

  def test_duplicates_in_unions(self):
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
    ast = self.ParseAndResolve(src)
    optimized = self.Optimize(ast, lossy=False, max_union=2)
    optimized = optimized.Visit(visitors.DropBuiltinPrefix())
    self.AssertSourceEquals(optimized, new_src)

  def test_simplify_unions(self):
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

  def test_factorize(self):
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
        def foo(a: float, x: complex or str) -> file
        def foo(a: int, x: file, ...) -> file
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.Factorize()), new_src)

  def test_factorize_mutable(self):
    src = textwrap.dedent("""
        def foo(a: list[bool], b: X) -> file:
            a = list[int]
        def foo(a: list[bool], b: Y) -> file:
            a = list[int]
        # not groupable:
        def bar(a: int, b: list[int]) -> file:
            b = list[complex]
        def bar(a: int, b: list[float]) -> file:
            b = list[str]
    """)
    new_src = textwrap.dedent("""
        def foo(a: list[bool], b: X or Y) -> file:
            a = list[int]
        def bar(a: int, b: list[int]) -> file:
            b = list[complex]
        def bar(a: int, b: list[float]) -> file:
            b = list[str]
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, optimize.Factorize()), new_src)

  def test_optional_arguments(self):
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

  def test_builtin_superclasses(self):
    src = textwrap.dedent("""
        def f(x: list or object, y: complex or memoryview) -> int or bool
    """)
    expected = textwrap.dedent("""
        def f(x: object, y: object) -> int
    """)
    hierarchy = self.builtins.Visit(visitors.ExtractSuperClassesByName())
    hierarchy.update(self.typing.Visit(visitors.ExtractSuperClassesByName()))
    visitor = optimize.FindCommonSuperClasses(
        optimize.SuperClassHierarchy(hierarchy))
    ast = self.ParseAndResolve(src)
    ast = ast.Visit(visitor)
    ast = ast.Visit(visitors.DropBuiltinPrefix())
    ast = ast.Visit(visitors.CanonicalOrderingVisitor())
    self.AssertSourceEquals(ast, expected)

  def test_user_superclass_hierarchy(self):
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
        def g(x: object) -> EFG
        def h(x) -> ?
    """) + class_data

    hierarchy = self.Parse(src).Visit(
        visitors.ExtractSuperClassesByName())
    visitor = optimize.FindCommonSuperClasses(
        optimize.SuperClassHierarchy(hierarchy))
    new_src = self.ApplyVisitorToString(src, visitor)
    self.AssertSourceEquals(new_src, expected)

  def test_find_common_superclasses(self):
    src = textwrap.dedent("""
        x = ...  # type: int or other.Bar
    """)
    expected = textwrap.dedent("""
        x = ...  # type: int or other.Bar
    """)
    ast = self.Parse(src)
    ast = ast.Visit(visitors.ReplaceTypes(
        {"other.Bar": pytd.LateType("other.Bar")}))
    hierarchy = ast.Visit(visitors.ExtractSuperClassesByName())
    ast = ast.Visit(optimize.FindCommonSuperClasses(
        optimize.SuperClassHierarchy(hierarchy)))
    ast = ast.Visit(visitors.LateTypeToClassType())
    self.AssertSourceEquals(ast, expected)

  def test_simplify_unions_with_superclasses(self):
    src = textwrap.dedent("""
        x = ...  # type: int or bool
        y = ...  # type: int or bool or float
        z = ...  # type: list[int] or int
    """)
    expected = textwrap.dedent("""
        x = ...  # type: int
        y = ...  # type: int or float
        z = ...  # type: list[int] or int
    """)
    hierarchy = self.builtins.Visit(visitors.ExtractSuperClassesByName())
    visitor = optimize.SimplifyUnionsWithSuperclasses(
        optimize.SuperClassHierarchy(hierarchy))
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, self.builtins)
    ast = ast.Visit(visitor)
    self.AssertSourceEquals(ast, expected)

  @unittest.skip("Needs better handling of GenericType")
  def test_simplify_unions_with_superclasses_generic(self):
    src = textwrap.dedent("""
        x = ...  # type: frozenset[int] or AbstractSet[int]
    """)
    expected = textwrap.dedent("""
        x = ...  # type: AbstractSet[int]
    """)
    hierarchy = self.builtins.Visit(visitors.ExtractSuperClassesByName())
    visitor = optimize.SimplifyUnionsWithSuperclasses(
        optimize.SuperClassHierarchy(hierarchy))
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, self.builtins)
    ast = ast.Visit(visitor)
    self.AssertSourceEquals(ast, expected)

  def test_collapse_long_unions(self):
    src = textwrap.dedent("""
        def f(x: A or B or C or D) -> X
        def g(x: A or B or C or D or E) -> X
        def h(x: A or ?) -> X
    """)
    expected = textwrap.dedent("""
        def f(x: A or B or C or D) -> X
        def g(x) -> X
        def h(x) -> X
    """)
    ast = self.ParseAndResolve(src)
    ast = ast.Visit(optimize.CollapseLongUnions(max_length=4))
    ast = ast.Visit(visitors.DropBuiltinPrefix())
    self.AssertSourceEquals(ast, expected)

  def test_collapse_long_constant_unions(self):
    src = textwrap.dedent("""
      x = ...  # type: A or B or C or D
      y = ...  # type: A or B or C or D or E
    """)
    expected = textwrap.dedent("""
      x = ...  # type: A or B or C or D
      y = ...  # type: ?
    """)
    ast = self.ParseAndResolve(src)
    ast = ast.Visit(optimize.CollapseLongUnions(max_length=4))
    ast = ast.Visit(optimize.AdjustReturnAndConstantGenericType())
    self.AssertSourceEquals(ast, expected)

  def test_combine_containers(self):
    src = textwrap.dedent("""
        def f(x: list[int] or list[float]) -> ?
        def g(x: list[int] or str or list[float] or set[int] or long) -> ?
        def h(x: list[int] or list[str] or set[int] or set[float]) -> ?
        def i(x: list[int] or list[int]) -> ?
        def j(x: dict[int, float] or dict[float, int]) -> ?
        def k(x: dict[int, bool] or list[int] or dict[bool, int] or list[bool]) -> ?
    """)
    expected = textwrap.dedent("""
        def f(x: list[float]) -> ?: ...
        def g(x: list[float] or str or set[int] or long) -> ?: ...
        def h(x: list[int or str] or set[float]) -> ?: ...
        def i(x: list[int]) -> ?: ...
        def j(x: dict[float, float]) -> ?: ...
        def k(x: dict[int or bool, bool or int] or list[int or bool]) -> ?: ...
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def test_combine_containers_multi_level(self):
    src = textwrap.dedent("""
      v = ...  # type: list[tuple[long or int, ...]] or list[tuple[float or bool, ...]]
    """)
    expected = textwrap.dedent("""
      v = ...  # type: list[tuple[long or int or float or bool, ...]]
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def test_combine_same_length_tuples(self):
    src = textwrap.dedent("""
      x = ...  # type: tuple[int] or tuple[str]
    """)
    expected = textwrap.dedent("""
      x = ...  # type: tuple[int or str]
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def test_combine_different_length_tuples(self):
    src = textwrap.dedent("""
      x = ...  # type: tuple[int] or tuple[int, str]
    """)
    expected = textwrap.dedent("""
      x = ...  # type: tuple[int or str, ...]
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def test_combine_different_length_callables(self):
    src = textwrap.dedent("""
      from typing import Callable
      x = ...  # type: Callable[[int], str] or Callable[[int, int], str]
    """)
    expected = textwrap.dedent("""
      from typing import Callable
      x = ...  # type: Callable[..., str]
    """)
    new_src = self.ApplyVisitorToString(src, optimize.CombineContainers())
    self.AssertSourceEquals(new_src, expected)

  def test_pull_in_method_classes(self):
    src = textwrap.dedent("""
        class A(object):
            mymethod1 = ...  # type: Method1
            mymethod2 = ...  # type: Method2
            member = ...  # type: Method3
            mymethod4 = ...  # type: Method4
        class Method1(object):
            def __call__(self: A, x: int) -> ?
        class Method2(object):
            def __call__(self: object, x: int) -> ?
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

  def test_add_inherited_methods(self):
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
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, self.builtins)
    six.assertCountEqual(self,
                         ("g", "h"), [m.name for m in ast.Lookup("B").methods])
    ast = ast.Visit(optimize.AddInheritedMethods())
    six.assertCountEqual(self, ("f", "g", "h"),
                         [m.name for m in ast.Lookup("B").methods])

  def test_adjust_inherited_method_self(self):
    src = textwrap.dedent("""
      class A():
        def f(self: object) -> float
      class B(A):
        pass
    """)
    ast = self.Parse(src)
    ast = visitors.LookupClasses(ast, self.builtins)
    ast = ast.Visit(optimize.AddInheritedMethods())
    self.assertMultiLineEqual(pytd_utils.Print(ast.Lookup("B")),
                              textwrap.dedent("""
        class B(A):
            def f(self) -> float: ...
    """).lstrip())

  def test_absorb_mutable_parameters(self):
    src = textwrap.dedent("""
        def popall(x: list[?]) -> ?:
            x = list[nothing]
        def add_float(x: list[int]) -> ?:
            x = list[int or float]
        def f(x: list[int]) -> ?:
            x = list[int or float]
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

  def test_absorb_mutable_parameters_from_methods(self):
    # This is a test for intermediate data. See AbsorbMutableParameters class
    # pydoc about how AbsorbMutableParameters works on methods.
    src = textwrap.dedent("""
        T = TypeVar('T')
        NEW = TypeVar('NEW')
        class MyClass(typing.Generic[T], object):
            def append(self, x: NEW) -> ?:
                self = MyClass[T or NEW]
    """)
    expected = textwrap.dedent("""
        T = TypeVar('T')
        NEW = TypeVar('NEW')
        class MyClass(typing.Generic[T], object):
            def append(self: MyClass[T or NEW], x: NEW) -> ?
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(optimize.AbsorbMutableParameters())
    new_tree = new_tree.Visit(optimize.CombineContainers())
    self.AssertSourceEquals(new_tree, expected)

  def test_merge_type_parameters(self):
    # This test uses pytd of the kind that's typically the output of
    # AbsorbMutableParameters.
    # See comment in RemoveMutableParameters
    src = textwrap.dedent("""
      T = TypeVar('T')
      T2 = TypeVar('T2')
      T3 = TypeVar('T3')
      class A(typing.Generic[T], object):
          def foo(self, x: T or T2) -> T2
          def bar(self, x: T or T2 or T3) -> T3
          def baz(self, x: T or T2, y: T2 or T3) -> ?

      K = TypeVar('K')
      V = TypeVar('V')
      class D(typing.Generic[K, V], object):
          def foo(self, x: T) -> K or T
          def bar(self, x: T) -> V or T
          def baz(self, x: K or V) -> K or V
          def lorem(self, x: T) -> T or K or V
          def ipsum(self, x: T) -> T or K
    """)
    expected = textwrap.dedent("""
      T = TypeVar('T')
      T2 = TypeVar('T2')
      T3 = TypeVar('T3')
      class A(typing.Generic[T], object):
          def foo(self, x: T) -> T
          def bar(self, x: T) -> T
          def baz(self, x: T, y: T) -> ?

      K = TypeVar('K')
      V = TypeVar('V')
      class D(typing.Generic[K, V], object):
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
