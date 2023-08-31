"""Tests for typing.TypedDict."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypedDictTest(test_base.BaseTest):
  """Tests for typing.TypedDict."""

  def test_init(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y='2')
      b = A(x=1, y=2)  # wrong-arg-types[e1]
      c = A(x=1)  # missing-parameter[e2]
      d = A(y='1')  # missing-parameter
      e = A(1, '2')  # missing-parameter
    """)
    self.assertErrorSequences(err, {
        "e1": ["Expected", "(*, x, y: str)", "Actual", "(x, y: int)"],
        "e2": ["Expected", "(*, x, y)", "Actual", "(x)"]
    })

  def test_key_error(self):
    # TODO(b/63407497): Enabling --strict-parameter-checks leads to an extra
    # wrong-arg-types error on line 8.
    self.options.tweak(strict_parameter_checks=False)
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y="2")
      a["z"] = 10  # typed-dict-error[e1]
      a[10] = 10  # typed-dict-error[e2]
      b = a["z"]  # typed-dict-error
      del a["z"]  # typed-dict-error
    """)
    self.assertErrorSequences(err, {
        "e1": ["TypedDict A", "key z"],
        "e2": ["TypedDict A", "requires all keys", "strings"],
    })

  def test_value_error(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a = A(x=1, y="2")
      a["x"] = "10"  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Type annotation", "key x", "TypedDict A",
        "Annotation: int", "Assignment: str"
    ]})

  def test_union_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      from typing import Union
      class A(TypedDict):
        x: Union[int, str]
        y: Union[int, str]
      a = A(x=1, y="2")
      a["x"] = "10"
      a["y"] = []  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Type annotation", "key y", "TypedDict A",
        "Annotation: Union[int, str]", "Assignment: List[nothing]"
    ]})

  def test_bad_base_class(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo: pass
      class Bar(TypedDict, Foo):  # base-class-error[e]
        x: int
    """)
    self.assertErrorSequences(err, {"e": [
        "Invalid base class", "Foo", "TypedDict Bar", "cannot inherit"
    ]})

  def test_inheritance(self):
    self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
      class Bar(TypedDict):
        y: str
      class Baz(Foo, Bar):
        z: bool
      a = Baz(x=1, y='2', z=False)
      a['x'] = 1
      a['y'] = 2  # annotation-type-mismatch
      a['z'] = True
      a['w'] = True  # typed-dict-error
    """)

  def test_inheritance_clash(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
      class Bar(TypedDict):
        y: str
      class Baz(Foo, Bar):  # base-class-error[e]
        x: bool
    """)
    self.assertErrorSequences(err, {"e": [
        "Duplicate", "key x", "Foo", "Baz"
    ]})

  def test_annotation(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      a: A = {'x': '10', 'z': 20}  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Annotation: A(TypedDict)",
        "extra keys", "z",
        "type errors", "{'x': ...}", "expected int", "got str"
    ]})

  def test_annotated_global_var(self):
    ty = self.Infer("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
      a: A = {'x': 10}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict

      class A(TypedDict):
        x: int

      a: A
    """)

  def test_annotated_local_var(self):
    ty = self.Infer("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
      def f():
        a: A = {'x': 10}
        return a
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict

      class A(TypedDict):
        x: int

      def f() -> A: ...
    """)

  def test_return_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      def f() -> A:
        return {'x': '10', 'z': 20}  # bad-return-type[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Expected: A(TypedDict)",
        "extra keys", "z",
        "type errors", "{'x': ...}", "expected int", "got str"
    ]})

  def test_total_with_constructor(self):
    self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict, total=True):
        w: int
        x: int
      class Bar(TypedDict, total=False):
        y: str
        z: bool
      class Baz(Foo, Bar):
        a: int
      a = Baz(w=1, x=1, y='2', z=False, a=2)
      b = Baz(w=1, x=1, a=2)
      c = Baz(w=1, x=1, y='2')  # missing-parameter
      d = Baz(w=1, x=1, a=2, b=3)  # wrong-keyword-args
    """)

  def test_total_with_annotation(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class Foo(TypedDict, total=True):
        w: int
        x: int
      class Bar(TypedDict, total=False):
        y: str
        z: bool
      class Baz(Foo, Bar):
        a: int
      a: Baz = {'w': 1, 'x': 1, 'y': '2', 'z': False, 'a': 2}
      b: Baz = {'w': 1, 'x': 1, 'a': 2}
      c: Baz = {'w': 1, 'y': '2', 'z': False, 'a': 2}  # annotation-type-mismatch[e1]
      d: Baz = {'w': 1, 'x': 1, 'y': '2', 'b': False, 'a': 2}  # annotation-type-mismatch[e2]
    """)
    self.assertErrorSequences(err, {
        "e1": ["missing keys", "x"],
        "e2": ["extra keys", "b"],
    })

  def test_function_arg_matching(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      def f(a: A):
        pass
      a: A = {'x': 10, 'y': 'a'}
      b = {'x': 10, 'y': 'a'}
      c = {'x': 10}
      f(a)
      f(b)
      f(c)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(err, {"e": ["TypedDict", "missing keys", "y"]})

  def test_function_arg_instantiation(self):
    self.CheckWithErrors("""
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: str
      def f(a: A):
        a['z'] = 10  # typed-dict-error
    """)

  def test_function_arg_getitem(self):
    self.CheckWithErrors("""
      from typing import Union
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
        y: Union[int, str]
      def f(a: A) -> int:
        assert_type(a['x'], int)
        assert_type(a['y'], Union[int, str])
        return a['z']  # typed-dict-error
    """)

  def test_output_type(self):
    ty = self.Infer("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
        y: str

      def f(x: Foo) -> None:
        pass

      foo = Foo(x=1, y="2")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict

      foo: Foo

      class Foo(TypedDict):
        x: int
        y: str

      def f(x: Foo) -> None: ...
    """)

  def test_instantiate(self):
    self.Check("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: int
      def f(x: Foo):
        pass
      x: Foo
      f(x)
    """)

  def test_key_existence_check(self):
    self.Check("""
      from typing import Union
      from typing_extensions import TypedDict

      class Foo(TypedDict):
        a: int
      class Bar(TypedDict):
        b: str
      class Baz(TypedDict):
        c: Union[Foo, Bar]

      baz: Baz = {'c': {'a': 0}}
      assert 'a' in baz['c']
      print(baz['c']['a'])
    """)

  def test_get(self):
    self.Check("""
      from typing_extensions import TypedDict
      class X(TypedDict):
        a: int
        b: str
      def f(x: X):
        assert_type(x.get('a'), int)
        assert_type(x.get('c'), None)
        assert_type(x.get('c', ''), str)
    """)

  def test_generic_holder(self):
    self.Check("""
      from dataclasses import dataclass
      from typing import Generic, TypeVar
      from typing_extensions import TypedDict

      T = TypeVar('T')

      class Animal(TypedDict):
        name: str

      @dataclass
      class GenericHolder(Generic[T]):
        a: T
        def get(self) -> T:
          return self.a

      class AnimalHolder(GenericHolder[Animal]):
        def get2(self) -> Animal:
          return self.get()
    """)

  def test_match_mapping(self):
    self.CheckWithErrors("""
      from typing import Mapping
      from typing_extensions import TypedDict
      class A(TypedDict):
        x: int
      def f1(a: Mapping[str, int]):
        pass
      def f2(a: Mapping[int, str]):
        pass
      f1(A(x=0))  # ok
      f2(A(x=0))  # wrong-arg-types
    """)

  def test_typed_dict_dataclass(self):
    self.Check("""
      import dataclasses
      from typing_extensions import TypedDict
      @dataclasses.dataclass
      class A(TypedDict):
        x: int
      def f():
        return A(x=0)
    """)

  def test_iterable_generic_class_and_recursive_type_interaction(self):
    with self.DepTree([("foo.pyi", """
      from typing import Any, Generic, Iterable, TypeVar, Union
      _ShapeType = TypeVar('_ShapeType')
      _DType = TypeVar('_DType')
      class ndarray(Generic[_ShapeType, _DType]):
        def __iter__(self) -> Any: ...
      ArrayTree = Union[Iterable[ArrayTree], ndarray]
    """)]):
      self.Check("""
        import foo
        from typing_extensions import TypedDict
        class TD(TypedDict):
          x: foo.ArrayTree
        def f() -> TD:
          return __any_object__
      """)


class TypedDictFunctionalTest(test_base.BaseTest):
  """Tests for typing.TypedDict functional constructor."""

  def test_constructor(self):
    self.CheckWithErrors("""
      from typing_extensions import TypedDict
      A = TypedDict("A", {"x": int, "y": str})
      B = TypedDict("B", "b")  # wrong-arg-types
      C = TypedDict("C")  # wrong-arg-count
    """)

  def test_init(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      A = TypedDict("A", {"x": int, "y": str})
      a = A(x=1, y='2')
      b = A(x=1, y=2)  # wrong-arg-types[e1]
      c = A(x=1)  # missing-parameter[e2]
      d = A(y='1')  # missing-parameter
      e = A(1, '2')  # missing-parameter
    """)
    self.assertErrorSequences(err, {
        "e1": ["Expected", "(*, x, y: str)", "Actual", "(x, y: int)"],
        "e2": ["Expected", "(*, x, y)", "Actual", "(x)"]
    })

  def test_annotation(self):
    err = self.CheckWithErrors("""
      from typing_extensions import TypedDict
      A = TypedDict("A", {"x": int, "y": str})
      a: A = {'x': '10', 'z': 20}  # annotation-type-mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": [
        "Annotation: A(TypedDict)",
        "extra keys", "z",
        "type errors", "{'x': ...}", "expected int", "got str"
    ]})

  def test_keyword_field_name(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypedDict
      A = TypedDict("A", {"in": int})
    """)]):
      self.Check("""
        import foo
        a: foo.A
        assert_type(a["in"], int)
      """)

  def test_colon_field_name(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypedDict
      XMLDict = TypedDict("XMLDict", {"xml:name": str})
    """)]):
      self.Check("""
        import foo
        d: foo.XMLDict
        assert_type(d["xml:name"], str)
      """)

  def test_total(self):
    ty = self.Infer("""
      from typing_extensions import TypedDict
      X = TypedDict('X', {'name': str}, total=False)
      X()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict, total=False):
        name: str
    """)


_SINGLE = """
  from typing import TypedDict
  class A(TypedDict):
    x: int
    y: str
"""

_MULTIPLE = """
  from typing import TypedDict
  class A(TypedDict):
    x: int
    y: str

  class B(A):
    z: int
"""


class PyiTypedDictTest(test_base.BaseTest):
  """Tests for typing.TypedDict in pyi files."""

  def test_basic(self):
    with self.DepTree([("foo.pyi", _SINGLE)]):
      self.CheckWithErrors("""
        from foo import A
        a = A(x=1, y='2')
        b = A(x=1, y=2)  # wrong-arg-types
      """)

  def test_function_arg(self):
    with self.DepTree([("foo.pyi", _SINGLE)]):
      self.CheckWithErrors("""
        from foo import A
        def f(d: A) -> str:
          a = d['x']
          assert_type(a, int)
          b = d['z']  # typed-dict-error
          return d['y']
      """)

  def test_function_return_type(self):
    with self.DepTree([("foo.pyi", _SINGLE)]):
      self.Check("""
        from foo import A
        def f() -> A:
          return {'x': 1, 'y': '2'}
      """)

  def test_inheritance(self):
    with self.DepTree([("foo.pyi", _SINGLE)]):
      self.CheckWithErrors("""
        from foo import A
        class B(A):
          z: int
        def f() -> B:
          return {'x': 1, 'y': '2', 'z': 3}
        def g() -> B:
          return {'x': 1, 'y': '2'}  # bad-return-type
      """)

  def test_pyi_inheritance(self):
    with self.DepTree([("foo.pyi", _MULTIPLE)]):
      self.CheckWithErrors("""
        from foo import A, B
        def f() -> B:
          return {'x': 1, 'y': '2', 'z': 3}
        def g() -> B:
          return {'x': 1, 'y': '2'}  # bad-return-type
      """)

  def test_multi_module_pyi_inheritance(self):
    with self.DepTree([
        ("foo.pyi", _MULTIPLE),
        ("bar.pyi", """
         from foo import B
         class C(B):
           w: int
         """)
    ]):
      self.CheckWithErrors("""
        from bar import C
        def f() -> C:
          return {'x': 1, 'y': '2', 'z': 3, 'w': 4}
        a = C(x=1, y='2', z=3, w='4')  # wrong-arg-types
      """)

  def test_typing_extensions_import(self):
    with self.DepTree([
        ("foo.pyi", """
         from typing_extensions import TypedDict
         class A(TypedDict):
           x: int
           y: str
         """)
    ]):
      self.CheckWithErrors("""
        from foo import A
        a = A(x=1, y='2')
        b = A(x=1, y=2)  # wrong-arg-types
      """)

  def test_full_name(self):
    with self.DepTree([("foo.pyi", _SINGLE)]):
      err = self.CheckWithErrors("""
        import foo
        from typing_extensions import TypedDict
        class A(TypedDict):
          z: int
        def f(x: A):
          pass
        def g() -> foo.A:
          return {'x': 1, 'y': '2'}
        a = g()
        f(a)  # wrong-arg-types[e]
      """)
      self.assertErrorSequences(err, {"e": [
          "Expected", "x: A", "Actual", "x: foo.A"
      ]})

  def test_setitem(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypedDict
      class Foo(TypedDict):
        x: int
    """), ("bar.pyi", """
      import foo
      def f() -> foo.Foo: ...
    """)]):
      self.Check("""
        import bar
        foo = bar.f()
        foo['x'] = 42
      """)

  def test_match(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypedDict
      class Foo(TypedDict):
        x: int
      def f(x: Foo) -> None: ...
      def g() -> Foo: ...
    """)]):
      self.Check("""
        import foo
        foo.f(foo.g())
      """)

  def test_nested(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypedDict
      class Foo:
        class Bar(TypedDict):
          x: str
    """)]):
      self.CheckWithErrors("""
        import foo
        foo.Foo.Bar(x='')  # ok
        foo.Foo.Bar(x=0)  # wrong-arg-types
      """)

  def test_imported_and_nested(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: str
    """)]):
      ty = self.Infer("""
        import foo
        class Bar:
          Foo = foo.Foo
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      class Bar:
        Foo: type[foo.Foo]
    """)

  def test_nested_alias(self):
    ty = self.Infer("""
      from typing_extensions import TypedDict
      class Foo(TypedDict):
        x: str
      class Bar:
        Foo = Foo
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class Foo(TypedDict):
        x: str
      class Bar:
        Foo: type[Foo]
    """)

  def test_total_false(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import TypedDict
      class Foo(TypedDict, total=False):
        x: str
        y: int
    """), ("bar.pyi", """
      from typing import TypedDict
      class Bar(TypedDict, total=False):
        x: str
        y: int
    """)]):
      self.Check("""
        import foo
        import bar
        foo.Foo(x='hello')
        bar.Bar(x='world')
      """)

  def test_total_inheritance(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypedDict
      class Parent1(TypedDict, total=True):
        x: str
      class Child1(Parent1, total=False):
        y: int
      class Parent2(TypedDict, total=False):
        x: str
      class Child2(Parent2, total=True):
        y: int
    """)]):
      self.CheckWithErrors("""
        import foo
        foo.Child1(x='')
        foo.Child1(y=0)  # missing-parameter
        foo.Child2(x='')  # missing-parameter
        foo.Child2(y=0)
      """)


class IsTypedDictTest(test_base.BaseTest):
  """Tests for typing.is_typeddict.

  These tests define variables based on the result of is_typeddict, allowing us
  to verify the result based on whether the corresponding variable appears in
  the pytd.
  """

  def test_basic(self):
    ty = self.Infer("""
      from typing_extensions import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      if is_typeddict(X):
        X_is_typeddict = True
      else:
        X_is_not_typeddict = True
      if is_typeddict(Y):
        Y_is_typeddict = True
      else:
        Y_is_not_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      X_is_typeddict: bool
      Y_is_not_typeddict: bool
    """)

  def test_pyi(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
    """)]):
      ty = self.Infer("""
        import foo
        from typing_extensions import is_typeddict
        if is_typeddict(foo.X):
          X_is_typeddict = True
        else:
          X_is_not_typeddict = True
        if is_typeddict(foo.Y):
          Y_is_typeddict = True
        else:
          Y_is_not_typeddict = True
      """)
      self.assertTypesMatchPytd(ty, """
        import foo
        X_is_typeddict: bool
        Y_is_not_typeddict: bool
      """)

  @test_utils.skipBeforePy((3, 10), "is_typeddict is new in Python 3.10.")
  def test_from_typing(self):
    ty = self.Infer("""
      from typing import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      if is_typeddict(X):
        X_is_typeddict = True
      else:
        X_is_not_typeddict = True
      if is_typeddict(Y):
        Y_is_typeddict = True
      else:
        Y_is_not_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      X_is_typeddict: bool
      Y_is_not_typeddict: bool
    """)

  def test_union(self):
    ty = self.Infer("""
      from typing import Union
      from typing_extensions import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y(TypedDict):
        y: int
      class Z:
        z: bytes
      if is_typeddict(Union[X, Y]):
        XY_is_typeddict = True
      else:
        XY_is_not_typeddict = True
      if is_typeddict(Union[X, Z]):
        XZ_is_typeddict = True
      else:
        XZ_is_not_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y(TypedDict):
        y: int
      class Z:
        z: bytes
      XY_is_typeddict: bool
      XZ_is_not_typeddict: bool
    """)

  def test_split(self):
    ty = self.Infer("""
      from typing_extensions import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      cls = X if __random__ else Y
      if is_typeddict(cls):
        XY_may_be_typeddict = True
      else:
        XY_may_not_be_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      cls: type[X | Y]
      XY_may_be_typeddict: bool
      XY_may_not_be_typeddict: bool
    """)

  def test_namedarg(self):
    ty = self.Infer("""
      from typing_extensions import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      if is_typeddict(tp=X):
        X_is_typeddict = True
      else:
        X_is_not_typeddict = True
      if is_typeddict(tp=Y):
        Y_is_typeddict = True
      else:
        Y_is_not_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y:
        y: int
      X_is_typeddict: bool
      Y_is_not_typeddict: bool
    """)

  def test_ambiguous(self):
    ty = self.Infer("""
      from typing_extensions import is_typeddict
      if is_typeddict(*__any_object__, **__any_object__):
        ambiguous_may_be_typeddict = True
      else:
        ambiguous_may_not_be_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      ambiguous_may_be_typeddict: bool
      ambiguous_may_not_be_typeddict: bool
    """)

  def test_subclass(self):
    ty = self.Infer("""
      from typing_extensions import is_typeddict, TypedDict
      class X(TypedDict):
        x: str
      class Y(X):
        pass
      if is_typeddict(Y):
        Y_is_typeddict = True
      else:
        Y_is_not_typeddict = True
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypedDict
      class X(TypedDict):
        x: str
      class Y(TypedDict):
        x: str
      Y_is_typeddict: bool
    """)

  def test_bad_args(self):
    self.CheckWithErrors("""
      from typing_extensions import is_typeddict
      is_typeddict()  # missing-parameter
      is_typeddict(__any_object__, __any_object__)  # wrong-arg-count
      is_typeddict(toilet_paper=True)  # wrong-keyword-args
    """)


if __name__ == "__main__":
  test_base.main()
