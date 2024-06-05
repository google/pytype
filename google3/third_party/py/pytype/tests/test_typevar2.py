"""Tests for TypeVar."""

import sys

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class TypeVarTest(test_base.BaseTest):
  """Tests for TypeVar."""

  def test_id(self):
    ty = self.Infer("""
      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
      w = f("")
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      from typing import Any
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
      w = ...  # type: str
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def test_extract_item(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S")  # unused
      T = TypeVar("T")
      def f(x: List[T]) -> T:
        return __any_object__
      v = f(["hello world"])
      w = f([True])
    """)
    self.assertTypesMatchPytd(ty, """
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: typing.List[T]) -> T: ...
      v = ...  # type: str
      w = ...  # type: bool
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def test_wrap_item(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar("T")
      def f(x: T) -> List[T]:
        return __any_object__
      v = f(True)
      w = f(3.14)
    """)
    self.assertTypesMatchPytd(ty, """
      T = TypeVar("T")
      def f(x: T) -> typing.List[T]: ...
      v = ...  # type: typing.List[bool]
      w = ...  # type: typing.List[float]
    """)

  def test_import_typevar_name_change(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        X = TypeVar("X")
      """)
      _, errors = self.InferWithErrors("""
        # This is illegal: A TypeVar("T") needs to be stored under the name "T".
        from a import T as T2  # invalid-typevar[e1]
        from a import X
        Y = X  # invalid-typevar[e2]
        def f(x: T2) -> T2: ...
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e1": r"T.*T2", "e2": r"X.*Y"})

  def test_typevar_in_typevar(self):
    self.CheckWithErrors("""
      from typing import Generic, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      S1 = TypeVar('S1', bound=T1)  # invalid-typevar
      S2 = TypeVar('S2', T1, T2)  # invalid-typevar
      # Using the invalid TypeVar should not produce an error.
      class Foo(Generic[S1]):
        pass
    """)

  def test_multiple_substitution(self):
    ty = self.Infer("""
      from typing import Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]:
        return __any_object__
      v = f({})
      w = f({"test": 42})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]: ...
      v = ...  # type: Tuple[Any, Any]
      w = ...  # type: Tuple[int, str]
    """)

  def test_union(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]:
        return __any_object__
      v = f("", 42)
      w = f(3.14, False)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      S = TypeVar("S")
      T = TypeVar("T")
      def f(x: S, y: T) -> Union[S, T]: ...
      v = ...  # type: Union[str, int]
      w = ...  # type: Union[float, bool]
    """)

  def test_bad_substitution(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar
      S = TypeVar("S")
      T = TypeVar("T")
      def f1(x: S) -> List[S]:
        return {x}  # bad-return-type[e1]
      def f2(x: S) -> S:
        return 42  # no error because never called
      def f3(x: S) -> S:
        return 42  # bad-return-type[e2]  # bad-return-type[e3]
      def f4(x: S, y: T, z: T) -> List[S]:
        return [y]  # bad-return-type[e4]
      f3("")
      f3(16)  # ok
      f3(False)
      f4(True, 3.14, 0)
      f4("hello", "world", "domination")  # ok
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"list.*set", "e2": r"str.*int", "e3": r"bool.*int",
        "e4": r"List\[bool\].*List\[Union\[float, int\]\]"})

  def test_use_constraints(self):
    ty, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T) -> T:
        return __any_object__
      v = f("")  # wrong-arg-types[e]
      w = f(True)  # ok
      u = f(__any_object__)  # ok
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar, Union
      T = TypeVar("T", int, float)
      def f(x: T) -> T: ...
      v = ...  # type: Any
      w = ...  # type: bool
      u = ...  # type: Union[int, float]
    """)
    self.assertErrorRegexes(errors, {"e": r"Union\[float, int\].*str"})

  def test_type_parameter_type(self):
    ty = self.Infer("""
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T:
        return __any_object__
      v = f(int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      T = TypeVar("T")
      def f(x: Type[T]) -> T: ...
      v = ...  # type: int
    """)

  def test_type_parameter_type_error(self):
    errors = self.CheckWithErrors("""
      from typing import Sequence, Type, TypeVar
      T = TypeVar('T')
      def f(x: int):
        pass
      def g(x: Type[Sequence[T]]) -> T:
        print(f(x))  # wrong-arg-types[e]
        return x()[0]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*int.*Actual.*Type\[Sequence\]"})

  def test_print_nested_type_parameter(self):
    _, errors = self.InferWithErrors("""
      from typing import List, TypeVar
      T = TypeVar("T", int, float)
      def f(x: List[T]): ...
      f([""])  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {
        "e": r"List\[Union\[float, int\]\].*List\[str\]"})

  def test_constraint_subtyping(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float)
      def f(x: T, y: T): ...
      f(True, False)  # ok
      f(True, 42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Expected.*y: bool.*Actual.*y: int"})

  def test_filter_value(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", str, float)
      def f(x: T, y: T): ...
      x = ''
      x = 42.0
      f(x, '')  # wrong-arg-types[e]
      f(x, 42.0)  # ok
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*y: float.*Actual.*y: str"})

  def test_filter_class(self):
    self.Check("""
      from typing import TypeVar
      class A: pass
      class B: pass
      T = TypeVar("T", A, B)
      def f(x: T, y: T): ...
      x = A()
      x.__class__ = B
      # Setting __class__ makes the type ambiguous to pytype.
      f(x, A())
      f(x, B())
    """)

  def test_split(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T", int, type(None))
      def f(x: T) -> T:
        return __any_object__
      if __random__:
        x = None
      else:
        x = 3
      v = id(x) if x else 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, TypeVar
      v = ...  # type: int
      x = ...  # type: Optional[int]
      T = TypeVar("T", int, None)
      def f(x: T) -> T: ...
    """)

  def test_enforce_non_constrained_typevar(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T")
      def f(x: T, y: T): ...
      f(42, True)  # ok
      f(42, "")  # wrong-arg-types[e1]
      f(42, 16j)  # ok
      f(object(), 42)  # ok
      f(42, object())  # ok
      f(42.0, "")  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Expected.*y: int.*Actual.*y: str",
        "e2": r"Expected.*y: float.*Actual.*y: str"})

  def test_useless_typevar(self):
    self.InferWithErrors("""
      from typing import Tuple, TypeVar
      T = TypeVar("T")
      S = TypeVar("S", int, float)
      def f1(x: T): ...  # invalid-annotation
      def f2() -> T: ...  # invalid-annotation
      def f3(x: Tuple[T]): ...  # invalid-annotation
      def f4(x: Tuple[T, T]): ...  # ok
      def f5(x: S): ...  # ok
      def f6(x: "U"): ...  # invalid-annotation
      def f7(x: T, y: "T"): ...  # ok
      def f8(x: "U") -> "U": ...  # ok
      U = TypeVar("U")
    """)

  def test_use_bound(self):
    ty, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T:
        return x
      v1 = f(__any_object__)  # ok
      v2 = f(True)  # ok
      v3 = f(42)  # ok
      v4 = f(3.14)  # ok
      v5 = f("")  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T: ...
      v1 = ...  # type: float
      v2 = ...  # type: bool
      v3 = ...  # type: int
      v4 = ...  # type: float
      v5 = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"x: float.*x: str"})

  def test_bad_return(self):
    self.assertNoCrash(self.Check, """
      from typing import AnyStr, Dict

      class Foo:
        def f(self) -> AnyStr: return __any_object__
        def g(self) -> Dict[AnyStr, Dict[AnyStr, AnyStr]]:
          return {'foo': {'bar': self.f()}}
    """)

  def test_optional_typevar(self):
    _, errors = self.InferWithErrors("""
      from typing import Optional, TypeVar
      T = TypeVar("T", bound=str)
      def f() -> Optional[T]:
        return 42 if __random__ else None  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Optional\[str\].*int"})

  def test_unicode_literals(self):
    ty = self.Infer("""
      from __future__ import unicode_literals
      import typing
      T = typing.TypeVar("T")
      def f(x: T) -> T:
        return __any_object__
      v = f(42)
    """)
    self.assertTypesMatchPytd(ty, """
      import typing
      from typing import Any
      T = TypeVar("T")
      def f(x: T) -> T: ...
      v = ...  # type: int
    """)

  def test_any_as_bound(self):
    self.Check("""
      from typing import Any, TypeVar
      T = TypeVar("T", bound=Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)

  def test_any_as_constraint(self):
    self.Check("""
      from typing import Any, TypeVar
      T = TypeVar("T", str, Any)
      def f(x: T) -> T:
        return x
      f(42)
    """)

  def test_name_reuse(self):
    self.Check("""
      from typing import Generic, TypeVar
      T = TypeVar("T", int, float)
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
      def f(foo: Foo[T]) -> T:
        return foo.x
    """)

  def test_property_type_param(self):
    # We should allow property signatures of the form f(self) -> X[T] without
    # needing to annotate 'self' if the class is generic and we use its type
    # parameter in the property's signature.
    ty = self.Infer("""
      from typing import TypeVar, Generic
      T = TypeVar('T')
      class A(Generic[T]):
          def __init__(self, foo: T):
              self._foo = foo
          @property
          def foo(self) -> T:
              return self._foo
          @foo.setter
          def foo(self, foo: T) -> None:
              self._foo = foo
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Generic, Any, Annotated
      T = TypeVar('T')
      class A(Generic[T]):
          _foo: T
          foo: Annotated[T, 'property']
          def __init__(self, foo: T) -> None:
            self = A[T]
    """)

  @test_base.skip("Needs improvements to matcher.py to detect error.")
  def test_return_typevar(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T) -> T:
        return T  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": "Expected.*T.*Actual.*TypeVar"})

  def test_typevar_in_union_alias(self):
    ty = self.Infer("""
      from typing import Dict, List, TypeVar, Union
      T = TypeVar("T")
      U = TypeVar("U")
      Foo = Union[T, List[T], Dict[T, List[U]], complex]
      def f(x: Foo[int, str]): ...
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, TypeVar, Union
      T = TypeVar("T")
      U = TypeVar("U")
      Foo = Union[T, List[T], Dict[T, List[U]], complex]
      def f(x: Union[Dict[int, List[str]], List[int], complex, int]) -> None: ...
    """)

  def test_typevar_in_union_alias_error(self):
    err = self.CheckWithErrors("""
      from typing import Dict, List, TypeVar, Union
      T = TypeVar("T")
      U = TypeVar("U")
      Foo = Union[T, List[T], Dict[T, List[U]], complex]
      def f(x: Foo[int]): ...  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(err, {"e": "Union.*2.*got.*1"})

  def test_cast_generic_tuple(self):
    self.Check("""
      from typing import Tuple, TypeVar, cast
      T = TypeVar('T')
      def f(x: T, y: T):
        return cast(Tuple[T, ...], x)
      assert_type(f(0, 1), Tuple[int, ...])
    """)

  def test_cast_in_instance_method(self):
    self.Check("""
      from typing import TypeVar, cast
      T = TypeVar('T', bound='Base')
      class Base:
        def clone(self: T) -> T:
          return cast(T, __any_object__)
      class Child(Base):
        pass
      Child().clone()
    """)

  def test_typevar_in_nested_function(self):
    self.Check("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T):
        def wrapper(x: T):
          pass
        return wrapper
    """)

  def test_typevar_in_nested_function_in_instance_method(self):
    self.Check("""
      from typing import TypeVar
      T = TypeVar('T')
      class Foo:
        def f(self, x: T):
          def g(x: T):
            pass
    """)

  def test_pass_through_class(self):
    self.Check("""
      from typing import Type, TypeVar
      T = TypeVar('T')
      def f(cls: Type[T]) -> Type[T]:
        return cls
    """)

  @test_base.skip("Requires completing TODO in annotation_utils.deformalize")
  def test_type_of_typevar(self):
    self.Check("""
      from typing import Type, TypeVar
      T = TypeVar('T', bound=int)
      class Foo:
        def f(self, x: T) -> Type[T]:
          return type(x)
        def g(self):
          assert_type(self.f(0), Type[int])
    """)

  def test_instantiate_unsubstituted_typevar(self):
    # TODO(b/79369981): Report an error for T appearing only once in f.
    self.Check("""
      from typing import Type, TypeVar
      T = TypeVar('T', bound=int)
      def f() -> Type[T]:
        return int
      def g():
        return f().__name__
    """)

  def test_class_typevar_in_nested_method(self):
    self.Check("""
      from typing import Generic, TypeVar
      T = TypeVar('T')
      class Foo(Generic[T]):
        def __init__(self, x: T):
          self.x = x
        def f(self):
          def g() -> T:
            return self.x
          return g()
      assert_type(Foo(0).f(), int)
    """)

  def test_self_annotation_in_base_class(self):
    self.Check("""
      from typing import TypeVar
      T = TypeVar('T', bound='Base')
      class Base:
        def resolve(self: T) -> T:
          return self
      class Child(Base):
        def resolve(self: T) -> T:
          assert_type(Base().resolve(), Base)
          return self
      assert_type(Child().resolve(), Child)
    """)

  def test_union_against_typevar(self):
    self.Check("""
      from typing import Callable, Iterable, TypeVar, Union
      T = TypeVar('T')
      def f(x: Callable[[T], int], y: Iterable[T]):
        pass

      def g(x: Union[int, str]):
        return 0

      f(g, [0, ''])
    """)

  def test_callable_instance_against_callable(self):
    self.CheckWithErrors("""
      from typing import Any, Callable, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2', bound=int)

      def f() -> Callable[[T2], T2]:
        return __any_object__

      # Passing f() to g is an error because g expects a callable with an
      # unconstrained parameter type.
      def g(x: Callable[[T1], T1]):
        pass
      g(f())  # wrong-arg-types

      # Passing f() to h is okay because T1 in this Callable is just being used
      # to save the parameter type for h's return type.
      def h(x: Callable[[T1], Any]) -> T1:
        return __any_object__
      h(f())
    """)

  def test_future_annotations(self):
    self.Check("""
      from __future__ import annotations
      from typing import Callable, TypeVar
      T = TypeVar('T')
      x: Callable[[T], T] = lambda x: x
    """)

  def test_imported_typevar_in_scope(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar
      T = TypeVar('T')
    """)]):
      self.Check("""
        import foo
        def f(x: foo.T) -> foo.T:
          y: foo.T = x
          return y
      """)

  def test_bad_typevar_in_pyi(self):
    # TODO(rechen): We should report an error for the stray `T` in foo.C.f. For
    # now, just make sure this doesn't crash pytype.
    with self.DepTree([("foo.pyi", """
      from typing import Callable, TypeVar
      T = TypeVar('T')
      class C:
        f: Callable[..., T]
    """)]):
      self.assertNoCrash(self.Check, """
        import foo
        class C(foo.C):
          def g(self):
            return self.f(0)
      """)


class GenericTypeAliasTest(test_base.BaseTest):
  """Tests for generic type aliases ("type macros")."""

  def test_homogeneous_tuple(self):
    ty = self.Infer("""
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[T, ...]

      def f(x: X[int]):
        pass

      f((0, 1, 2))  # should not raise an error
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[T, ...]

      def f(x: Tuple[int, ...]) -> None: ...
    """)

  def test_heterogeneous_tuple(self):
    ty, _ = self.InferWithErrors("""
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[T]
      def f(x: X[int]):
        pass
      f((0, 1, 2))  # wrong-arg-types
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, TypeVar
      T = TypeVar('T')
      X = Tuple[T]
      def f(x: Tuple[int]) -> None: ...
    """)

  def test_substitute_typevar(self):
    foo_ty = self.Infer("""
      from typing import List, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = List[T1]
      def f(x: X[T2]) -> T2:
        return x[0]
    """)
    self.assertTypesMatchPytd(foo_ty, """
      from typing import List, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = List[T1]
      def f(x: List[T2]) -> T2: ...
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        def f(x: T) -> foo.X[T]:
          return [x]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import List, TypeVar
        T = TypeVar('T')
        def f(x: T) -> List[T]: ...
      """)

  def test_substitute_value(self):
    foo_ty = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar('T')
      X = List[T]
      def f(x: X[int]) -> int:
        return x[0]
    """)
    self.assertTypesMatchPytd(foo_ty, """
      from typing import List, TypeVar
      T = TypeVar('T')
      X = List[T]
      def f(x: List[int]) -> int: ...
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        def f(x: int) -> foo.X[int]:
          return [x]
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import List
        def f(x: int) -> List[int]: ...
      """)

  def test_partial_substitution(self):
    ty = self.Infer("""
      from typing import Dict, TypeVar
      T = TypeVar('T')
      X = Dict[T, str]
      def f(x: X[int]) -> int:
        return next(iter(x.keys()))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, TypeVar
      T = TypeVar('T')
      X = Dict[T, str]
      def f(x: Dict[int, str]) -> int: ...
    """)

  def test_callable(self):
    ty = self.Infer("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      X = Callable[[T], str]
      def f() -> X[int]:
        def g(x: int):
          return str(x)
        return g
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, TypeVar
      T = TypeVar('T')
      X = Callable[[T], str]
      def f() -> Callable[[int], str]: ...
    """)

  def test_import_callable(self):
    foo = self.Infer("""
      from typing import TypeVar
      T = TypeVar('T')
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      bar = self.Infer("""
        import foo
        from typing import Callable
        X = Callable[[foo.T], foo.T]
      """, pythonpath=[d.path])
      d.create_file("bar.pyi", pytd_utils.Print(bar))
      ty = self.Infer("""
        import foo
        import bar
        def f(x: foo.T, y: bar.X[foo.T]):
          pass
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import bar
        import foo
        from typing import Callable, TypeVar
        T = TypeVar('T')
        def f(x: T, y: Callable[[T], T]) -> None: ...
      """)

  def test_union_typevar(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Union[int, T1]
      def f(x: X[T2], y: T2):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Union[int, T1]
      def f(x: Union[int, T2], y: T2) -> None: ...
    """)

  def test_union_value(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      T = TypeVar('T')
      X = Union[int, T]
      def f(x: X[str]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union, TypeVar
      T = TypeVar('T')
      X = Union[int, T]
      def f(x: Union[int, str]) -> None: ...
    """)

  def test_extra_parameter(self):
    errors = self.CheckWithErrors("""
      from typing import Dict, TypeVar
      T = TypeVar('T')
      X = Dict[T, T]
      def f(x: X[int, str]):  # invalid-annotation[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"expected 1 parameter, got 2"})

  def test_missing_parameter(self):
    errors = self.CheckWithErrors("""
      from typing import Dict, TypeVar
      T1 = TypeVar('T1')
      T2 = TypeVar('T2')
      X = Dict[T1, T2]
      def f(x: X[int]):  # invalid-annotation[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"expected 2 parameters, got 1"})

  def test_nested_typevars(self):
    ty = self.Infer("""
      from typing import Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: X[float, str]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: Callable[[int], Dict[float, str]]) -> None: ...
    """)

  def test_extra_nested_parameter(self):
    ty, errors = self.InferWithErrors("""
      from typing import Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: X[float, str, complex]):  # invalid-annotation[e]
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: Callable[[int], Dict[float, str]]) -> None: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"expected 2 parameters, got 3"})

  def test_missing_nested_parameter(self):
    ty, errors = self.InferWithErrors("""
      from typing import Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: X[float]):  # invalid-annotation[e]
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable, Dict, TypeVar
      K = TypeVar('K')
      V = TypeVar('V')
      X = Callable[[int], Dict[K, V]]
      def f(x: Callable[[int], Dict[float, Any]]) -> None: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"expected 2 parameters, got 1"})

  def test_reingest_union(self):
    foo = self.Infer("""
      from typing import Optional, TypeVar
      T = TypeVar('T')
      X = Optional[T]
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      ty = self.Infer("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        def f1(x: foo.X[int]):
          pass
        def f2(x: foo.X[T]) -> T:
          assert x
          return x
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import Optional, TypeVar
      T = TypeVar('T')
      def f1(x: Optional[int]) -> None: ...
      def f2(x: Optional[T]) -> T: ...
    """)

  def test_multiple_options(self):
    # distilled from real user code
    ty = self.Infer("""
      from typing import Any, Mapping, Sequence, TypeVar, Union
      K = TypeVar('K')
      V = TypeVar('V')
      X = Union[Sequence, Mapping[K, Any], V]
      try:
        Y = X[str, V]
      except TypeError:
        Y = Union[Sequence, Mapping[str, Any], V]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Mapping, Sequence, TypeVar, Union
      K = TypeVar('K')
      V = TypeVar('V')
      X = Union[Sequence, Mapping[K, Any], V]
      Y = Union[Sequence, Mapping[str, Any], V]
    """)

  def test_multiple_typevar_options(self):
    ty = self.Infer("""
      from typing import TypeVar
      if __random__:
        T1 = TypeVar('T1')
        T2 = TypeVar('T2')
      else:
        T1 = TypeVar('T1')
        T2 = TypeVar('T2', bound=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      T1 = TypeVar('T1')
      T2: Any
    """)

  def test_unparameterized_typevar_alias(self):
    err = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T')
      U = TypeVar('U')
      Foo = list[T]
      Bar = dict[T, U]
      def f(x: Foo) -> int:  # invalid-annotation[e]
        return 42
      def g(x: Foo) -> T:
        return 42
      def h(x: Foo[T]) -> int:  # invalid-annotation
        return 42
      def h(x: Foo, y: Bar) -> int:  # invalid-annotation
        return 42
      def j(x: Foo, y: Bar, z: U) -> int:
        return 42
    """)
    if sys.version_info[:2] >= (3, 9):
      # In 3.9+, we use opcode metadata to produce a better error message for
      # bare generic aliases.
      self.assertErrorSequences(err, {"e": ["Foo is a generic alias"]})


class TypeVarTestPy3(test_base.BaseTest):
  """Tests for TypeVar in Python 3."""

  def test_use_constraints_from_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AnyStr, TypeVar
        T = TypeVar("T", int, float)
        def f(x: T) -> T: ...
        def g(x: AnyStr) -> AnyStr: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f("")  # wrong-arg-types[e1]
        foo.g(0)  # wrong-arg-types[e2]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {
          "e1": r"Union\[float, int\].*str",
          "e2": r"Union\[bytes, str\].*int"})

  def test_subprocess(self):
    ty = self.Infer("""
      import subprocess
      from typing import List
      def run(args: List[str]):
        result = subprocess.run(
          args,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          universal_newlines=True)
        if result.returncode:
          raise subprocess.CalledProcessError(
              result.returncode, args, result.stdout)
        return result.stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      from typing import List
      def run(args: List[str]) -> str: ...
    """)

  def test_abstract_classmethod(self):
    self.Check("""
      from abc import ABC, abstractmethod
      from typing import Type, TypeVar

      T = TypeVar('T', bound='Foo')

      class Foo(ABC):
        @classmethod
        @abstractmethod
        def f(cls: Type[T]) -> T:
          return cls()
    """)

  def test_split(self):
    self.Check("""
      from typing import AnyStr, Generic
      class Foo(Generic[AnyStr]):
        def __init__(self, x: AnyStr):
          if isinstance(x, str):
            self.x = x
          else:
            self.x = x.decode('utf-8')
    """)

  def test_typevar_in_variable_annotation(self):
    self.Check("""
      from typing import TypeVar
      T = TypeVar('T')
      def f(x: T):
        y: T = x
    """)

  def test_none_constraint(self):
    self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar('T', float, None)
      def f(x: T) -> T:
        return x
      f(0.0)
      f(None)
      f("oops")  # wrong-arg-types
    """)

  @test_utils.skipBeforePy((3, 9), "subscripting builtins.dict is new in 3.9")
  def test_builtin_dict_constraint(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar
      T = TypeVar('T', int, dict[str, int])
      class C:
        def f(self, x: T) -> T: ...
    """)]):
      self.Check("""
        import foo
        from typing import TypeVar
        T = TypeVar('T', int, dict[str, int])
        class C(foo.C):
          def f(self, x: T) -> T:
            return x
      """)


if __name__ == "__main__":
  test_base.main()
