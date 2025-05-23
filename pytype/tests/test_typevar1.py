"""Tests for TypeVar."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypeVarTest(test_base.BaseTest):
  """Tests for TypeVar."""

  def test_unused_typevar(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      T = TypeVar("T")
    """,
    )

  @test_utils.skipBeforePy((3, 12), "type aliases are new in 3.12")
  def test_unused_typevar_pep695(self):
    ty = self.Infer("""
      type MyType[T] = list[T]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      T = TypeVar("T")
      MyType = list[T]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "type aliases are new in 3.12")
  def test_unused_typevar_pep695_switch_order(self):
    ty = self.Infer("""
      type FlippedPair[S, T] = tuple[T, S]
    """)
    # TODO(b/412616662): This pytd result is wrong, as T and S order should be
    # flipped but there's no way to represent this properly without printing out
    # type aliases.
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      S = TypeVar('S')
      T = TypeVar("T")
      FlippedPair = tuple[T, S]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_type_var_with_bounds_in_type_alias(self):
    ty = self.Infer("""
      type Alias[T: int] = list[T]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      T = TypeVar('T', bound=int)
      Alias = list[T]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_type_var_with_constraints_in_type_alias(self):
    ty = self.Infer("""
      type Alias[T: (int, str)] = list[T]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      T = TypeVar('T', int, str)
      Alias = list[T]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_function_type_var_single(self):
    ty = self.Infer("""
      def foo[T, S](a: T) -> T:
        return a
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      T = TypeVar("T")

      def foo(a: T) -> T: ...
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_function_type_var_double(self):
    ty = self.Infer("""
      def foo[T, S](a: T, b: S) -> tuple[S, T]:
        return (a, b)
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      S = TypeVar('S')
      T = TypeVar('T')

      def foo(a: T, b: S) -> tuple[S, T]: ...
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_class_single_type_var(self):
    ty = self.Infer("""
      class A[T]: pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Generic, TypeVar

      T = TypeVar('T')

      class A(Generic[T]):
        __type_params__: tuple[Any]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_class_double_type_var(self):
    ty = self.Infer("""
      class A[T, S]: pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, Generic, TypeVar
      S = TypeVar('S')
      T = TypeVar('T')

      class A(Generic[T, S]):
        __type_params__: tuple[Any, Any]
    """,
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_type_var_tuple(self):
    errors = self.CheckWithErrors("""
      type Tup[*Ts] = ( # not-supported-yet[e1]
          tuple[int, *Ts] )  # invalid-annotation[e2]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": "Using TypeVarTuple in Generics is not supported yet",
            "e2": "Invalid type annotation '<instance of tuple>' \nNot a type",
        },
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_class_both_generic_and_base(self):
    errors = self.CheckWithErrors("""
      from typing import Generic, TypeVar
      U = TypeVar('U')
      class A[T, S](Generic[U]): pass # invalid-annotation[e1]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": (
                r"Invalid type annotation 'A' \nCannot inherit from"
                r" Generic\[...\] multiple times"
            ),
        },
    )

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_unused_typevar_pep695_class_inherit_from_base(self):
    ty = self.Infer("""
        class Base[T]: pass
        class Derived[S, T](Base[T]): pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
        from typing import Any, Generic, TypeVar
        S = TypeVar('S')
        T = TypeVar('T')

        class Base(Generic[T]):
          __type_params__: tuple[Any]
 
        class Derived(Base[T], Generic[S, T]):
          __type_params__: tuple[Any, Any]
    """,
    )

  def test_import_typevar(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """T = TypeVar("T")""")
      ty = self.Infer(
          """
        from a import T
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        from typing import TypeVar
        T = TypeVar("T")
      """,
      )

  def test_invalid_typevar(self):
    ty, errors = self.InferWithErrors("""
      from typing import TypeVar
      typevar = TypeVar
      T = typevar()  # invalid-typevar[e1]
      T = typevar("T")  # ok
      T = typevar(42)  # invalid-typevar[e2]
      T = typevar(str())  # invalid-typevar[e3]
      T = typevar("T", str, int if __random__ else float)  # invalid-typevar[e4]
      T = typevar("T", 0, float)  # invalid-typevar[e5]
      T = typevar("T", str)  # invalid-typevar[e6]
      # pytype: disable=not-supported-yet
      S = typevar("S", covariant=False)  # ok
      T = typevar("T", covariant=False)  # duplicate ok
      # pytype: enable=not-supported-yet
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar
      typevar = ...  # type: type
      S = TypeVar("S")
      T = TypeVar("T")
    """,
    )
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"wrong arguments",
            "e2": r"Expected.*str.*Actual.*int",
            "e3": r"constant str",
            "e4": r"constraint.*Must be constant",
            "e5": r"Expected.*_1:.*type.*Actual.*_1: int",
            "e6": r"0 or more than 1",
        },
    )

  def test_print_constraints(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S", int, float, covariant=True)  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """)
    # The "covariant" keyword is ignored for now.
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """,
    )

  def test_infer_typevars(self):
    ty = self.Infer("""
      def id(x):
        return x
      def wrap_tuple(x, y):
        return (x, y)
      def wrap_list(x, y):
        return [x, y]
      def wrap_dict(x, y):
        return {x: y}
      def return_second(x, y):
        return y
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, List, Tuple, Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def id(x: _T0) -> _T0: ...
      def wrap_tuple(x: _T0, y: _T1) -> Tuple[_T0, _T1]: ...
      def wrap_list(x: _T0, y: _T1) -> List[Union[_T0, _T1]]: ...
      def wrap_dict(x: _T0, y: _T1) -> Dict[_T0, _T1]: ...
      def return_second(x, y: _T1) -> _T1: ...
    """,
    )

  def test_infer_union(self):
    ty = self.Infer("""
      def return_either(x, y):
        return x or y
      def return_arg_or_42(x):
        return x or 42
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def return_either(x: _T0, y: _T1) -> Union[_T0, _T1]: ...
      def return_arg_or_42(x: _T0) -> Union[_T0, int]: ...
    """,
    )

  def test_typevar_in_type_comment(self):
    self.InferWithErrors("""
      from typing import List, TypeVar
      T = TypeVar("T")
      x = None  # type: T  # invalid-annotation
      y = None  # type: List[T]  # invalid-annotation
    """)

  def test_base_class_with_typevar(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar("T")
      class A(List[T]): pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, TypeVar
      T = TypeVar("T")
      class A(List[T]): ...
    """,
    )

  def test_overwrite_base_class_with_typevar(self):
    self.Check("""
      from typing import List, TypeVar
      T = TypeVar("T")
      l = List[T]
      l = list
      class X(l): pass
    """)

  def test_bound(self):
    self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", int, float, bound=str)  # invalid-typevar
      S = TypeVar("S", bound="")  # invalid-typevar
      V = TypeVar("V", bound=int if __random__ else float)  # invalid-typevar
      U = TypeVar("U", bound=str)  # ok
    """)

  def test_covariant(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", covariant=True)  # not-supported-yet
      U = TypeVar("U", covariant=True if __random__ else False)  # invalid-typevar[e1]
      S = TypeVar("S", covariant=42)  # invalid-typevar[e2]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"constant",
            "e2": r"Expected.*bool.*Actual.*int",
        },
    )

  def test_contravariant(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", contravariant=True)  # not-supported-yet
      U = TypeVar("U", contravariant=True if __random__ else False)  # invalid-typevar[e1]
      S = TypeVar("S", contravariant=42)  # invalid-typevar[e2]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"constant",
            "e2": r"Expected.*bool.*Actual.*int",
        },
    )

  def test_default(self):
    ty = self.Infer("""
      from typing import Generic, TypeVar

      T = TypeVar("T", default=int)  # pytype: disable=not-supported-yet

      class Foo(Generic[T]):
        pass

      f = Foo()
    """)
    self.assertTypesMatchPytd(
        ty,
        """
          from typing import Generic, TypeVar

          T = TypeVar('T')

          class Foo(Generic[T]): ...

          f: Foo[nothing]
        """,
    )

    self.CheckWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar("T", default=int)  # not-supported-yet

      class Foo(Generic[T]):
        pass

      f = Foo()
    """)

  def test_dont_propagate_pyval(self):
    # in functions like f(x: T) -> T, if T has constraints we should not copy
    # the value of constant types between instances of the typevar.
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
        from typing import TypeVar
        AnyInt = TypeVar('AnyInt', int)
        def f(x: AnyInt) -> AnyInt: ...
      """,
      )
      ty = self.Infer(
          """
        import a
        if a.f(0):
          x = 3
        if a.f(1):
          y = 3
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        x = ...  # type: int
        y = ...  # type: int
      """,
      )

  def test_property_type_param(self):
    # We should allow property signatures of the form f(self: T) -> X[T]
    # without complaining about the class not being parametrised over T
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, List
      T = TypeVar('T')
      class A:
          @property
          def foo(self: T) -> List[T]: ...
      class B(A): ...
      """,
      )
      ty = self.Infer(
          """
        import a
        x = a.A().foo
        y = a.B().foo
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import List
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """,
      )

  def test_property_type_param2(self):
    # Test for classes inheriting from Generic[X]
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[T]: ...
      class B(A, Generic[U]): ...
      def make_A() -> A[int]: ...
      def make_B() -> B[int]: ...
      """,
      )
      ty = self.Infer(
          """
        import a
        x = a.make_A().foo
        y = a.make_B().foo
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import List
        x = ...  # type: List[a.A[int]]
        y = ...  # type: List[a.B[int]]
      """,
      )

  # Skipping due to b/66005735
  @test_base.skip("Type parameter bug")
  def test_property_type_param3(self):
    # Don't mix up the class parameter and the property parameter
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[U]: ...
      def make_A() -> A[int]: ...
      """,
      )
      ty = self.Infer(
          """
        import a
        x = a.make_A().foo
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        x = ...  # type: List[int]
      """,
      )

  def test_property_type_param_with_constraints(self):
    # Test setting self to a constrained type
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U', int, str)
      X = TypeVar('X', int)
      class A(Generic[U]):
          @property
          def foo(self: A[X]) -> List[X]: ...
      def make_A() -> A[int]: ...
      """,
      )
      ty = self.Infer(
          """
        import a
        x = a.make_A().foo
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import List
        x = ...  # type: List[int]
      """,
      )

  def test_classmethod_type_param(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, List, Type
      T = TypeVar('T')
      class A:
          @classmethod
          def foo(self: Type[T]) -> List[T]: ...
      class B(A): ...
      """,
      )
      ty = self.Infer(
          """
        import a
        v = a.A.foo()
        w = a.B.foo()
        x = a.A().foo()
        y = a.B().foo()
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import List
        v = ...  # type: List[a.A]
        w = ...  # type: List[a.B]
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """,
      )

  def test_metaclass_property_type_param(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
      from typing import TypeVar, Type, List
      T = TypeVar('T')
      class Meta():
        @property
        def foo(self: Type[T]) -> List[T]: ...

      class A(metaclass=Meta):
        pass
      """,
      )
      ty = self.Infer(
          """
        import a
        x = a.A.foo
      """,
          pythonpath=[d.path],
      )
      self.assertTypesMatchPytd(
          ty,
          """
        import a
        from typing import List
        x = ...  # type: List[a.A]
      """,
      )

  def test_top_level_union(self):
    ty = self.Infer("""
      from typing import TypeVar
      if __random__:
        T = TypeVar("T")
      else:
        T = 42
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any
      T = ...  # type: Any
    """,
    )

  def test_store_typevar_in_dict(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
      a = {'key': T}
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, TypeVar
      a = ...  # type: Dict[str, nothing]
      T = TypeVar('T')
    """,
    )

  def test_late_bound(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar, Union
      T = TypeVar("T", int, float, bound="str")  # invalid-typevar[e1]
      S = TypeVar("S", bound="")  # invalid-typevar[e2]
      U = TypeVar("U", bound="str")  # ok
      V = TypeVar("V", bound="int if __random__ else float")  # invalid-typevar[e3]
      W = TypeVar("W", bound="Foo") # ok, forward reference
      X = TypeVar("X", bound="Bar")  # name-error[e4]
      class Foo:
        pass
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"mutually exclusive",
            "e2": r"empty string",
            "e3": r"Must be constant",
            "e4": r"Name.*Bar",
        },
    )

  def test_late_constraints(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", "int", "float")
      U = TypeVar("U", "List[int]", List[float])
      V = TypeVar("V", "Foo", "List[Foo]")
      class Foo:
        pass
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
      V = TypeVar("V", Foo, List[Foo])
      class Foo:
        pass
    """,
    )

  def test_typevar_in_alias(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      T = TypeVar("T", int, float)
      Num = Union[T, complex]
      x = 10  # type: Num[int]
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import TypeVar, Union
      T = TypeVar("T", int, float)
      Num = Union[T, complex]
      x: Union[int, complex]
    """,
    )

  def test_type_of_typevar(self):
    self.Check("""
      from typing import Sequence, TypeVar
      T = TypeVar('T')
      def f(x):  # type: (Sequence[T]) -> Sequence[T]
        print(type(x))
        return x
    """)

  def test_type_of_typevar_error(self):
    errors = self.CheckWithErrors("""
      from typing import Sequence, Type, TypeVar
      T = TypeVar('T')
      def f(x):  # type: (int) -> int
        return x
      def g(x):  # type: (Sequence[T]) -> Type[Sequence[T]]
        return f(type(x))  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": "Expected.*int.*Actual.*Sequence"})

  def test_typevar_in_constant(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar('T')
      class Foo:
        def __init__(self):
          self.f1 = self.f2
        def f2(self, x):
          # type: (T) -> T
          return x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Callable, TypeVar
      T = TypeVar('T')
      class Foo:
        f1: Callable[[T], T]
        def __init__(self) -> None: ...
        def f2(self, x: T) -> T: ...
    """,
    )

  def test_extra_arguments(self):
    errors = self.CheckWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", extra_arg=42)  # invalid-typevar[e1]
      S = TypeVar("S", *__any_object__)  # invalid-typevar[e2]
      U = TypeVar("U", **__any_object__)  # invalid-typevar[e3]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"extra_arg", "e2": r"\*args", "e3": r"\*\*kwargs"}
    )

  def test_simplify_args_and_kwargs(self):
    ty = self.Infer("""
      from typing import TypeVar
      constraints = (int, str)
      kwargs = {"covariant": True}
      T = TypeVar("T", *constraints, **kwargs)  # pytype: disable=not-supported-yet
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Dict, Tuple, Type, TypeVar
      T = TypeVar("T", int, str)
      constraints = ...  # type: Tuple[Type[int], Type[str]]
      kwargs = ...  # type: Dict[str, bool]
    """,
    )

  def test_typevar_starargs(self):
    with test_utils.Tempdir() as d:
      d.create_file(
          "a.pyi",
          """
        from typing import Generic, TypeVar, Union
        T = TypeVar('T')
        S = TypeVar('S')
        SS = TypeVar('SS')
        class A(Generic[T]):
          def __init__(self, x: T, *args: S, **kwargs: SS):
            self = A[Union[T, S, SS]]
      """,
      )
      self.Check(
          """
        import a
        a.A(1)
        a.A(1, 2, 3)
        a.A(1, 2, 3, a=1, b=2)
      """,
          pythonpath=[d.path],
      )

  def test_cast_generic_callable(self):
    errors = self.CheckWithErrors("""
      from typing import Callable, TypeVar, cast
      T = TypeVar('T')
      def f(x):
        return cast(Callable[[T, T], T], x)
      assert_type(f(None)(0, 1), int)
      f(None)(0, '1')  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": "Expected.*int.*Actual.*str"})

  @test_utils.skipBeforePy((3, 12), "PEP 695 - 3.12 feature")
  def test_global_var_not_hidden_by_type_variable(self):
    self.Check("""
      Apple: str = 'Apple'
      type AppleBox[Apple] = tuple[Apple, ...]
      def print_apple(a: str):
         print(a)
      print_apple(Apple)
    """)


if __name__ == "__main__":
  test_base.main()
