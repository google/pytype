import textwrap

from pytype.pytd import escape
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.pytd import visitors
from pytype.pytd.parse import parser_test_base
import six

import unittest


# All of these tests implicitly test pytd_utils.Print because
# parser_test_base.AssertSourceEquals() uses pytd_utils.Print.


DEFAULT_PYI = """
from typing import Any
def __getattr__(name) -> Any: ...
"""


def pytd_src(text):
  text = textwrap.dedent(escape.preprocess_pytd(text))
  text = text.replace("`", "")
  return text


class TestVisitors(parser_test_base.ParserTest):
  """Tests the classes in parse/visitors."""

  def test_invent_starargs_params(self):
    call = lambda x: tuple(f.name for f in visitors.InventStarArgParams(x))
    self.assertEqual(("args", "kwargs"), call({}))
    self.assertEqual(("args", "kwargs"), call({"a"}))
    self.assertEqual(("_args", "kwargs"), call({"args"}))
    self.assertEqual(("args", "_kwargs"), call({"kwargs"}))
    self.assertEqual(("_args", "_kwargs"), call({"args", "kwargs"}))
    self.assertEqual(("__args", "_kwargs"), call({"args", "_args", "kwargs"}))
    self.assertEqual(("args", "__kwargs"), call({"kwargs", "_kwargs"}))

  def test_lookup_classes(self):
    src = textwrap.dedent("""
        from typing import Union
        class object:
            pass

        class A:
            def a(self, a: A, b: B) -> Union[A, B]:
                raise A()
                raise B()

        class B:
            def b(self, a: A, b: B) -> Union[A, B]:
                raise A()
                raise B()
    """)
    tree = self.Parse(src)
    new_tree = visitors.LookupClasses(tree)
    self.AssertSourceEquals(new_tree, src)
    new_tree.Visit(visitors.VerifyLookup())

  def test_maybe_fill_in_local_pointers(self):
    src = textwrap.dedent("""
        from typing import Union
        class A:
            def a(self, a: A, b: B) -> Union[A, B]:
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

  def test_deface_unresolved(self):
    builtins = self.Parse(textwrap.dedent("""
      class int:
        pass
    """))
    src = textwrap.dedent("""
        class A(X):
            def a(self, a: A, b: X, c: int) -> X:
                raise X()
            def b(self) -> X[int]: ...
    """)
    expected = textwrap.dedent("""
        from typing import Any
        class A(Any):
            def a(self, a: A, b: Any, c: int) -> Any:
                raise Any
            def b(self) -> Any: ...
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    new_tree.Visit(visitors.VerifyVisitor())
    self.AssertSourceEquals(new_tree, expected)

  def test_deface_unresolved2(self):
    builtins = self.Parse(textwrap.dedent("""
      from typing import Generic, TypeVar
      class int:
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
            def c(self) -> Union[list[X], int]: ...
    """)
    expected = textwrap.dedent("""
        from typing import Any, Union
        class A(Any):
            def a(self, a: A, b: Any, c: int) -> Any:
                raise Any
            def c(self) -> Union[list[Any], int]: ...
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.DefaceUnresolved([tree, builtins]))
    new_tree.Visit(visitors.VerifyVisitor())
    self.AssertSourceEquals(new_tree, expected)

  def test_replace_types(self):
    src = textwrap.dedent("""
        from typing import Union
        class A:
            def a(self, a: Union[A, B]) -> Union[A, B]:
                raise A()
                raise B()
    """)
    expected = textwrap.dedent("""
        from typing import Union
        class A:
            def a(self: A2, a: Union[A2, B]) -> Union[A2, B]:
                raise A2()
                raise B()
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.ReplaceTypes({"A": pytd.NamedType("A2")}))
    self.AssertSourceEquals(new_tree, expected)

  def test_superclasses_by_name(self):
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
    six.assertCountEqual(self, ("object",), data["A"])
    six.assertCountEqual(self, ("object",), data["B"])
    six.assertCountEqual(self, ("A",), data["C"])
    six.assertCountEqual(self, ("A", "B"), data["D"])
    six.assertCountEqual(self, ("A", "C", "D"), data["E"])

  def test_strip_self(self):
    src = textwrap.dedent("""
        def add(x: int, y: int) -> int: ...
        class A:
            def bar(self, x: int) -> float: ...
            def baz(self) -> float: ...
            def foo(self, x: int, y: float) -> float: ...
    """)
    expected = textwrap.dedent("""
        def add(x: int, y: int) -> int: ...

        class A:
            def bar(x: int) -> float: ...
            def baz() -> float: ...
            def foo(x: int, y: float) -> float: ...
    """)
    tree = self.Parse(src)
    new_tree = tree.Visit(visitors.StripSelf())
    self.AssertSourceEquals(new_tree, expected)

  def test_remove_unknown_classes(self):
    src = pytd_src("""
        from typing import Union
        class `~unknown1`():
            pass
        class `~unknown2`():
            pass
        class A:
            def foobar(x: `~unknown1`, y: `~unknown2`) -> Union[`~unknown1`, int]: ...
    """)
    expected = textwrap.dedent("""
        from typing import Any, Union
        class A:
            def foobar(x, y) -> Union[Any, int]: ...
    """)
    tree = self.Parse(src)
    tree = tree.Visit(visitors.RemoveUnknownClasses())
    tree = tree.Visit(visitors.DropBuiltinPrefix())
    self.AssertSourceEquals(tree, expected)

  def test_find_unknown_visitor(self):
    src = pytd_src("""
        from typing import Any
        class object:
          pass
        class `~unknown1`():
          pass
        class `~unknown_foobar`():
          pass
        class `~int`():
          pass
        class A():
          def foobar(self, x: `~unknown1`) -> Any: ...
        class B():
          def foobar(self, x: `~int`) -> Any: ...
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

  def test_in_place_lookup_external_classes(self):
    src1 = textwrap.dedent("""
      def f1() -> bar.Bar: ...
      class Foo:
        pass
    """)
    src2 = textwrap.dedent("""
      def f2() -> foo.Foo: ...
      class Bar:
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

  def test_lookup_constant(self):
    src1 = textwrap.dedent("""
      Foo = ...  # type: type
    """)
    src2 = textwrap.dedent("""
      class Bar:
        bar = ...  # type: foo.Foo
    """)
    ast1 = self.Parse(src1, name="foo").Visit(
        visitors.LookupBuiltins(self.loader.builtins))
    ast2 = self.Parse(src2, name="bar")
    ast2 = ast2.Visit(visitors.LookupExternalTypes({"foo": ast1, "bar": ast2}))
    self.assertEqual(ast2.Lookup("bar.Bar").constants[0],
                     pytd.Constant(name="bar", type=pytd.AnythingType()))

  def test_lookup_star_alias(self):
    src1 = textwrap.dedent("""
      x = ...  # type: int
      T = TypeVar("T")
      class A: ...
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

  def test_lookup_star_alias_in_unnamed_module(self):
    src1 = textwrap.dedent("""
      class A: ...
    """)
    src2 = "from foo import *"
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2)
    name = ast2.name
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1}, self_name=None))
    self.assertEqual(name, ast2.name)
    self.assertMultiLineEqual(pytd_utils.Print(ast2), textwrap.dedent("""
      import foo

      A = foo.A
    """).strip())

  def test_lookup_two_star_aliases(self):
    src1 = "class A: ..."
    src2 = "class B: ..."
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

  def test_lookup_two_star_aliases_with_same_class(self):
    src1 = "class A: ..."
    src2 = "class A: ..."
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    self.assertRaises(KeyError, ast3.Visit, visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))

  def test_lookup_star_alias_with_duplicate_class(self):
    src1 = "class A: ..."
    src2 = textwrap.dedent("""
      from foo import *
      class A:
        x = ...  # type: int
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd_utils.Print(ast2), textwrap.dedent("""
      class bar.A:
          x: int
    """).strip())

  def test_lookup_two_star_aliases_with_default_pyi(self):
    src1 = DEFAULT_PYI
    src2 = DEFAULT_PYI
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    ast3 = ast3.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))
    self.assertMultiLineEqual(pytd_utils.Print(ast3), textwrap.dedent("""
      from typing import Any

      def baz.__getattr__(name) -> Any: ...
    """).strip())

  def test_lookup_star_alias_with_duplicate_getattr(self):
    src1 = DEFAULT_PYI
    src2 = textwrap.dedent("""
      from typing import Any
      from foo import *
      def __getattr__(name) -> Any: ...
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd_utils.Print(ast2), textwrap.dedent("""
      from typing import Any

      def bar.__getattr__(name) -> Any: ...
    """).strip())

  def test_lookup_two_star_aliases_with_different_getattrs(self):
    src1 = "def __getattr__(name) -> int: ..."
    src2 = "def __getattr__(name) -> str: ..."
    src3 = textwrap.dedent("""
      from foo import *
      from bar import *
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast3 = self.Parse(src3).Replace(name="baz").Visit(visitors.AddNamePrefix())
    self.assertRaises(KeyError, ast3.Visit, visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2, "baz": ast3}, self_name="baz"))

  def test_lookup_star_alias_with_different_getattr(self):
    src1 = "def __getattr__(name) -> int: ..."
    src2 = textwrap.dedent("""
      from foo import *
      def __getattr__(name) -> str: ...
    """)
    ast1 = self.Parse(src1).Replace(name="foo").Visit(visitors.AddNamePrefix())
    ast2 = self.Parse(src2).Replace(name="bar").Visit(visitors.AddNamePrefix())
    ast2 = ast2.Visit(visitors.LookupExternalTypes(
        {"foo": ast1, "bar": ast2}, self_name="bar"))
    self.assertMultiLineEqual(pytd_utils.Print(ast2), textwrap.dedent("""
      def bar.__getattr__(name) -> str: ...
    """).strip())

  def test_collect_dependencies(self):
    src = textwrap.dedent("""
      from typing import Union
      l = ... # type: list[Union[int, baz.BigInt]]
      def f1() -> bar.Bar: ...
      def f2() -> foo.bar.Baz: ...
    """)
    deps = visitors.CollectDependencies()
    self.Parse(src).Visit(deps)
    six.assertCountEqual(self, {"baz", "bar", "foo.bar"}, deps.dependencies)

  def test_expand(self):
    src = textwrap.dedent("""
        from typing import Union
        def foo(a: Union[int, float], z: Union[complex, str], u: bool) -> file: ...
        def bar(a: int) -> Union[str, unicode]: ...
    """)
    new_src = textwrap.dedent("""
        from typing import Union
        def foo(a: int, z: complex, u: bool) -> file: ...
        def foo(a: int, z: str, u: bool) -> file: ...
        def foo(a: float, z: complex, u: bool) -> file: ...
        def foo(a: float, z: str, u: bool) -> file: ...
        def bar(a: int) -> Union[str, unicode]: ...
    """)
    self.AssertSourceEquals(
        self.ApplyVisitorToString(src, visitors.ExpandSignatures()),
        new_src)

  def test_print_imports(self):
    src = textwrap.dedent("""
      from typing import Any, List, Tuple, Union
      def f(x: Union[int, slice]) -> List[Any]: ...
      def g(x: foo.C.C2) -> None: ...
    """)
    expected = textwrap.dedent("""
      import foo.C
      from typing import Any, List, Union

      def f(x: Union[int, slice]) -> List[Any]: ...
      def g(x: foo.C.C2) -> None: ...
    """).strip()
    tree = self.Parse(src)
    res = pytd_utils.Print(tree)
    self.AssertSourceEquals(res, src)
    self.assertMultiLineEqual(res, expected)

  def test_print_imports_named_type(self):
    # Can't get tree by parsing so build explicitly
    node = pytd.Constant("x", pytd.NamedType("typing.List"))
    tree = pytd_utils.CreateModule(name=None, constants=(node,))
    expected_src = textwrap.dedent("""
      from typing import List

      x: List
    """).strip()
    res = pytd_utils.Print(tree)
    self.assertMultiLineEqual(res, expected_src)

  def test_print_imports_ignores_existing(self):
    src = "from foo import b"

    tree = self.Parse(src)
    res = pytd_utils.Print(tree)
    self.assertMultiLineEqual(res, src)

  @unittest.skip("depended on `or`")
  def test_print_union_name_conflict(self):
    src = textwrap.dedent("""
      class Union: ...
      def g(x: Union) -> Union[int, float]: ...
    """)
    tree = self.Parse(src)
    res = pytd_utils.Print(tree)
    self.AssertSourceEquals(res, src)

  def test_adjust_type_parameters(self):
    ast = self.Parse("""
      from typing import Union
      T = TypeVar("T")
      T2 = TypeVar("T2")
      def f(x: T) -> T: ...
      class A(Generic[T]):
        def a(self, x: T2) -> None:
          self = A[Union[T, T2]]
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

  def test_adjust_type_parameters_with_builtins(self):
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

  def test_adjust_type_parameters_with_duplicates(self):
    ast = self.ParseWithBuiltins("""
      T = TypeVar("T")
      class A(Dict[T, T], Generic[T]): pass
    """)
    a = ast.Lookup("A")
    self.assertEqual(
        (pytd.TemplateItem(pytd.TypeParameter("T", (), None, "A")),),
        a.template)

  def test_adjust_type_parameters_with_duplicates_in_generic(self):
    src = textwrap.dedent("""
      T = TypeVar("T")
      class A(Generic[T, T]): pass
    """)
    self.assertRaises(visitors.ContainerError, lambda: self.Parse(src))

  def test_verify_containers(self):
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

  def test_clear_class_pointers(self):
    cls = pytd.Class("foo", None, (), (), (), (), (), None, ())
    t = pytd.ClassType("foo", cls)
    t = t.Visit(visitors.ClearClassPointers())
    self.assertIsNone(t.cls)

  def test_expand_compatible_builtins(self):
    src = textwrap.dedent("""
        from typing import Tuple, Union, TypeVar

        T = TypeVar('T', float, bool)

        def f1(a: float) -> None: ...
        def f2() -> float: ...

        def f3(a: bool) -> None: ...
        def f4() -> bool: ...

        def f5(a: Union[bool, int]) -> None: ...
        def f6(a: Tuple[bool, int]) -> None: ...

        def f7(x: T) -> T: ...
    """)
    expected = textwrap.dedent("""
        from typing import Tuple, TypeVar, Union

        T = TypeVar('T', float, bool)

        def f1(a: Union[float, int]) -> None: ...
        def f2() -> float: ...

        def f3(a: Union[bool, None]) -> None: ...
        def f4() -> bool: ...

        def f5(a: Union[bool, None, int]) -> None: ...
        def f6(a: Tuple[Union[bool, None], int]) -> None: ...

        def f7(x: T) -> T: ...
    """)

    src_tree, expected_tree = (
        self.Parse(s).Visit(visitors.LookupBuiltins(self.loader.builtins))
        for s in (src, expected))
    new_tree = src_tree.Visit(visitors.ExpandCompatibleBuiltins(
        self.loader.builtins))
    self.AssertSourceEquals(new_tree, expected_tree)

  def test_add_name_prefix(self):
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

  def test_add_name_prefix_twice(self):
    src = textwrap.dedent("""
      from typing import Any, TypeVar
      x = ...  # type: Any
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

  def test_add_name_prefix_on_class_type(self):
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

  def test_add_name_prefix_on_nested_class_alias(self):
    src = textwrap.dedent("""
      class A:
        class B:
          class C: ...
          D = A.B.C
    """)
    expected = textwrap.dedent("""
      from typing import Type

      class foo.A:
          class foo.A.B:
              class foo.A.B.C: ...
              D: Type[foo.A.B.C]
    """).strip()
    self.assertMultiLineEqual(expected, pytd_utils.Print(
        self.Parse(src).Replace(name="foo").Visit(visitors.AddNamePrefix())))

  def test_add_name_prefix_on_nested_class_outside_ref(self):
    src = textwrap.dedent("""
      class A:
        class B: ...
      b: A.B
      C = A.B
      def f(x: A.B) -> A.B: ...
      class D:
        b: A.B
        def f(self, x: A.B) -> A.B: ...
    """)
    expected = textwrap.dedent("""
      from typing import Type

      foo.b: foo.A.B
      foo.C: Type[foo.A.B]

      class foo.A:
          class foo.A.B: ...

      class foo.D:
          b: foo.A.B
          def f(self, x: foo.A.B) -> foo.A.B: ...

      def foo.f(x: foo.A.B) -> foo.A.B: ...
    """).strip()
    self.assertMultiLineEqual(expected, pytd_utils.Print(
        self.Parse(src).Replace(name="foo").Visit(visitors.AddNamePrefix())))

  def test_add_name_prefix_on_nested_class_method(self):
    src = textwrap.dedent("""
      class A:
        class B:
          def copy(self) -> A.B: ...
    """)
    expected = textwrap.dedent("""
      class foo.A:
          class foo.A.B:
              def copy(self) -> foo.A.B: ...
    """).strip()
    self.assertMultiLineEqual(expected, pytd_utils.Print(
        self.Parse(src).Replace(name="foo").Visit(visitors.AddNamePrefix())))

  def test_print_merge_types(self):
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
                              pytd_utils.Print(self.ToAST(src)).strip())

  def test_print_heterogeneous_tuple(self):
    t = pytd.TupleType(pytd.NamedType("tuple"),
                       (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertEqual("Tuple[str, float]", pytd_utils.Print(t))

  def test_verify_heterogeneous_tuple(self):
    # Error: does not inherit from Generic
    base = pytd.ClassType("tuple")
    base.cls = pytd.Class("tuple", None, (), (), (), (), (), None, ())
    t1 = pytd.TupleType(base, (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertRaises(visitors.ContainerError,
                      lambda: t1.Visit(visitors.VerifyContainers()))
    # Error: Generic[str, float]
    gen = pytd.ClassType("typing.Generic")
    gen.cls = pytd.Class("typing.Generic", None, (), (), (), (), (), None, ())
    t2 = pytd.TupleType(gen, (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertRaises(visitors.ContainerError,
                      lambda: t2.Visit(visitors.VerifyContainers()))
    # Okay
    param = pytd.TypeParameter("T")
    parent = pytd.GenericType(gen, (param,))
    base.cls = pytd.Class(
        "tuple", None, (parent,), (), (), (), (), None,
        (pytd.TemplateItem(param),))
    t3 = pytd.TupleType(base, (pytd.NamedType("str"), pytd.NamedType("float")))
    t3.Visit(visitors.VerifyContainers())

  def test_typevar_value_conflict(self):
    # Conflicting values for _T.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[int], List[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def test_typevar_value_conflict_hidden(self):
    # Conflicting value for _T hidden in MRO.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[int]): ...
      class B(A, List[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def test_typevar_value_conflict_related_containers(self):
    # List inherits from Sequence, so they share a type parameter.
    ast = self.ParseWithBuiltins("""
      from typing import List, Sequence
      class A(List[int], Sequence[str]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def test_typevar_value_no_conflict(self):
    # Not an error if the containers are unrelated, even if they use the same
    # type parameter name.
    ast = self.ParseWithBuiltins("""
      from typing import ContextManager, SupportsAbs
      class Foo(SupportsAbs[float], ContextManager[Foo]): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def test_typevar_value_consistency(self):
    # Type renaming makes all type parameters represent the same type `T1`.
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
      class D(C[str, str], A[str]): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def test_typevar_value_and_alias_conflict(self):
    ast = self.ParseWithBuiltins("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class A(Generic[T]): ...
      class B(A[int], A[T]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def test_typevar_alias_and_value_conflict(self):
    ast = self.ParseWithBuiltins("""
      from typing import Generic, TypeVar
      T = TypeVar("T")
      class A(Generic[T]): ...
      class B(A[T], A[int]): ...
    """)
    self.assertRaises(visitors.ContainerError,
                      lambda: ast.Visit(visitors.VerifyContainers()))

  def test_verify_container_with_mro_error(self):
    # Make sure we don't crash.
    ast = self.ParseWithBuiltins("""
      from typing import List
      class A(List[str]): ...
      class B(List[str], A): ...
    """)
    ast.Visit(visitors.VerifyContainers())

  def test_alias_printing(self):
    a = pytd.Alias("MyList", pytd.GenericType(
        pytd.NamedType("typing.List"), (pytd.AnythingType(),)))
    ty = pytd_utils.CreateModule("test", aliases=(a,))
    expected = textwrap.dedent("""
      from typing import Any, List

      MyList = List[Any]""")
    self.assertMultiLineEqual(expected.strip(), pytd_utils.Print(ty).strip())

  def test_print_none_union(self):
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
                              pytd_utils.Print(self.ToAST(src)).strip())

  def test_lookup_typing_class(self):
    node = visitors.LookupClasses(pytd.NamedType("typing.Sequence"),
                                  self.loader.concat_all())
    assert node.cls

  def test_create_type_parameters_from_unknowns(self):
    src = pytd_src("""
      from typing import Dict
      def f(x: `~unknown1`) -> `~unknown1`: ...
      def g(x: `~unknown2`, y: `~unknown2`) -> None: ...
      def h(x: `~unknown3`) -> None: ...
      def i(x: Dict[`~unknown4`, `~unknown4`]) -> None: ...

      # Should not be changed
      class `~unknown5`:
        def __add__(self, x: `~unknown6`) -> `~unknown6`: ...
      def `~f`(x: `~unknown7`) -> `~unknown7`: ...
    """)
    expected = pytd_src("""
      from typing import Dict

      _T0 = TypeVar('_T0')

      def f(x: _T0) -> _T0: ...
      def g(x: _T0, y: _T0) -> None: ...
      def h(x: `~unknown3`) -> None: ...
      def i(x: Dict[_T0, _T0]) -> None: ...

      class `~unknown5`:
        def __add__(self, x: `~unknown6`) -> `~unknown6`: ...
      def `~f`(x: `~unknown7`) -> `~unknown7`: ...
    """)
    ast1 = self.Parse(src)
    ast1 = ast1.Visit(visitors.CreateTypeParametersForSignatures())
    self.AssertSourceEquals(ast1, expected)

  @unittest.skip("We no longer support redefining TypeVar")
  def test_redefine_typevar(self):
    src = pytd_src("""
      def f(x: `~unknown1`) -> `~unknown1`: ...
      class `TypeVar`: ...
    """)
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd_utils.Print(ast), textwrap.dedent("""
      import typing

      _T0 = TypeVar('_T0')

      class `TypeVar`: ...

      def f(x: _T0) -> _T0: ...""").strip())

  def test_create_type_parameters_for_new(self):
    src = textwrap.dedent("""
      class Foo:
          def __new__(cls: Type[Foo]) -> Foo: ...
      class Bar:
          def __new__(cls: Type[Bar], x, y, z) -> Bar: ...
    """)
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd_utils.Print(ast), textwrap.dedent("""
      from typing import TypeVar

      _TBar = TypeVar('_TBar', bound=Bar)
      _TFoo = TypeVar('_TFoo', bound=Foo)

      class Foo:
          def __new__(cls: Type[_TFoo]) -> _TFoo: ...

      class Bar:
          def __new__(cls: Type[_TBar], x, y, z) -> _TBar: ...
    """).strip())

  def test_keep_custom_new(self):
    src = textwrap.dedent("""
      class Foo:
          def __new__(cls: Type[X]) -> X: ...

      class Bar:
          def __new__(cls, x: Type[Bar]) -> Bar: ...
    """).strip()
    ast = self.Parse(src).Visit(visitors.CreateTypeParametersForSignatures())
    self.assertMultiLineEqual(pytd_utils.Print(ast), src)

  def test_print_type_parameter_bound(self):
    src = textwrap.dedent("""
      from typing import TypeVar
      T = TypeVar("T", bound=str)
    """)
    self.assertMultiLineEqual(pytd_utils.Print(self.Parse(src)),
                              textwrap.dedent("""
      from typing import TypeVar

      T = TypeVar('T', bound=str)""").lstrip())

  def test_print_cls(self):
    src = textwrap.dedent("""
      class A:
          def __new__(cls: Type[A]) -> A: ...
    """)
    self.assertMultiLineEqual(pytd_utils.Print(self.Parse(src)),
                              textwrap.dedent("""
      class A:
          def __new__(cls) -> A: ...
    """).strip())

  def test_print_no_return(self):
    src = textwrap.dedent("""
      def f() -> nothing: ...
    """)
    self.assertMultiLineEqual(pytd_utils.Print(self.Parse(src)),
                              textwrap.dedent("""
      from typing import NoReturn

      def f() -> NoReturn: ...""").lstrip())

  def test_print_multiline_signature(self):
    src = textwrap.dedent("""
      def f(x: int, y: str, z: bool) -> list[str]:
        pass
    """)
    self.assertMultiLineEqual(
        pytd_utils.Print(self.Parse(src), multiline_args=True),
        textwrap.dedent("""
           from typing import List

           def f(
               x: int,
               y: str,
               z: bool
           ) -> List[str]: ...
        """).strip())

  def test_rename_builtins_prefix(self):
    """__builtin__.foo should get rewritten to builtins.foo and then to foo."""
    src = textwrap.dedent("""
      import __builtin__
      class MyError(__builtin__.KeyError): ...
    """)
    self.assertMultiLineEqual(pytd_utils.Print(self.Parse(src)),
                              "class MyError(KeyError): ...")


class ReplaceModulesWithAnyTest(unittest.TestCase):

  def test_any_replacement(self):
    class_type_match = pytd.ClassType("match.foo")
    named_type_match = pytd.NamedType("match.bar")
    class_type_no_match = pytd.ClassType("match_no.foo")
    named_type_no_match = pytd.NamedType("match_no.bar")
    generic_type_match = pytd.GenericType(class_type_match, ())
    generic_type_no_match = pytd.GenericType(class_type_no_match, ())

    visitor = visitors.ReplaceModulesWithAny(["match."])
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


class ReplaceUnionsWithAnyTest(unittest.TestCase):

  def test_any_replacement(self):
    union = pytd.UnionType((pytd.NamedType("a"), pytd.NamedType("b")))
    self.assertEqual(
        union.Visit(visitors.ReplaceUnionsWithAny()), pytd.AnythingType())


if __name__ == "__main__":
  unittest.main()
