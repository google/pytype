"""Tests for pytd_visitors."""

import textwrap

from pytype.pytd import pytd_visitors
from pytype.pytd import visitors
from pytype.pytd.parse import parser_test_base
import six

import unittest


class PytdVisitorsTest(parser_test_base.ParserTest):

  def test_rename_module(self):
    module_name = "foo.bar"
    src = """
        import module2
        from module2 import f
        from typing import List

        constant = True

        x = List[int]
        b = List[int]

        class SomeClass(object):
          def __init__(self, a: module2.ObjectMod2):
            pass

        def ModuleFunction():
          pass
    """
    ast = self.Parse(src, name=module_name)
    new_ast = ast.Visit(pytd_visitors.RenameModuleVisitor(module_name,
                                                          "other.name"))

    self.assertEqual("other.name", new_ast.name)
    self.assertTrue(new_ast.Lookup("other.name.SomeClass"))
    self.assertTrue(new_ast.Lookup("other.name.constant"))
    self.assertTrue(new_ast.Lookup("other.name.ModuleFunction"))

    with self.assertRaises(KeyError):
      new_ast.Lookup("foo.bar.SomeClass")

  def test_rename_module_with_type_parameter(self):
    module_name = "foo.bar"
    src = """
      import typing

      T = TypeVar('T')

      class SomeClass(typing.Generic[T]):
        def __init__(self, foo: T) -> None:
          pass
    """
    ast = self.Parse(src, name=module_name)
    new_ast = ast.Visit(pytd_visitors.RenameModuleVisitor(module_name,
                                                          "other.name"))

    some_class = new_ast.Lookup("other.name.SomeClass")
    self.assertTrue(some_class)
    init_function = some_class.Lookup("__init__")
    self.assertTrue(init_function)
    self.assertEqual(len(init_function.signatures), 1)
    signature, = init_function.signatures
    _, param2 = signature.params
    self.assertEqual(param2.type.scope, "other.name.SomeClass")

  def test_canonical_ordering_visitor(self):
    src1 = """
      from typing import Any, TypeVar, Union
      def f() -> Any:
        raise MemoryError()
        raise IOError()
      def f(x: list[a]) -> Any: ...
      def f(x: list[Union[b, c]]) -> Any: ...
      def f(x: list[tuple[d]]) -> Any: ...
      A = TypeVar("A")
      C = TypeVar("C")
      B = TypeVar("B")
      D = TypeVar("D")
      def f(d: A, c: B, b: C, a: D) -> Any: ...
    """
    src2 = """
      from typing import Any, Union
      def f() -> Any:
        raise IOError()
        raise MemoryError()
      def f(x: list[tuple[d]]) -> Any: ...
      def f(x: list[a]) -> Any: ...
      def f(x: list[Union[b, c]]) -> Any: ...
      A = TypeVar("A")
      C = TypeVar("C")
      B = TypeVar("B")
      D = TypeVar("D")
      def f(d: A, c: B, b: C, a: D) -> Any: ...
    """
    tree1 = self.Parse(src1)
    tree1 = tree1.Visit(
        pytd_visitors.CanonicalOrderingVisitor(sort_signatures=True))
    tree2 = self.Parse(src2)
    tree2 = tree2.Visit(
        pytd_visitors.CanonicalOrderingVisitor(sort_signatures=True))
    self.AssertSourceEquals(tree1, tree2)
    self.assertEqual(tree1.Lookup("f").signatures[0].template,
                     tree2.Lookup("f").signatures[0].template)

  def test_superclasses(self):
    src = textwrap.dedent("""
      class object:
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
    data = ast.Visit(pytd_visitors.ExtractSuperClasses())
    six.assertCountEqual(self,
                         ["object"], [t.name for t in data[ast.Lookup("A")]])
    six.assertCountEqual(self,
                         ["object"], [t.name for t in data[ast.Lookup("B")]])
    six.assertCountEqual(self, ["A"], [t.name for t in data[ast.Lookup("C")]])
    six.assertCountEqual(self,
                         ["A", "B"], [t.name for t in data[ast.Lookup("D")]])
    six.assertCountEqual(self, ["C", "D", "A"],
                         [t.name for t in data[ast.Lookup("E")]])


if __name__ == "__main__":
  unittest.main()
