"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class TypeVarTest(test_base.TargetIndependentTest):
  """Tests for TypeVar."""

  def test_unused_typevar(self):
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      T = TypeVar("T")
    """)

  def test_import_typevar(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """T = TypeVar("T")""")
      ty = self.Infer("""
        from a import T
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypeVar
        T = TypeVar("T")
      """)

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
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      typevar = ...  # type: type
      S = TypeVar("S")
      T = TypeVar("T")
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"wrong arguments", "e2": r"Expected.*str.*Actual.*int",
        "e3": r"constant str", "e4": r"constraint.*Must be constant",
        "e5": r"Expected.*_1:.*type.*Actual.*_1: int", "e6": r"0 or more than 1"
    })

  def test_print_constraints(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S", int, float, covariant=True)  # pytype: disable=not-supported-yet
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """, deep=False)
    # The "covariant" keyword is ignored for now.
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
    """)

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
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Tuple, Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def id(x: _T0) -> _T0: ...
      def wrap_tuple(x: _T0, y: _T1) -> Tuple[_T0, _T1]: ...
      def wrap_list(x: _T0, y: _T1) -> List[Union[_T0, _T1]]: ...
      def wrap_dict(x: _T0, y: _T1) -> Dict[_T0, _T1]: ...
      def return_second(x, y: _T1) -> _T1: ...
    """)

  def test_infer_union(self):
    ty = self.Infer("""
      def return_either(x, y):
        return x or y
      def return_arg_or_42(x):
        return x or 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      _T0 = TypeVar("_T0")
      _T1 = TypeVar("_T1")
      def return_either(x: _T0, y: _T1) -> Union[_T0, _T1]: ...
      def return_arg_or_42(x: _T0) -> Union[_T0, int]: ...
    """)

  def test_typevar_in_type_comment(self):
    self.InferWithErrors("""
      from typing import List, TypeVar
      T = TypeVar("T")
      x = None  # type: T  # not-supported-yet
      y = None  # type: List[T]  # not-supported-yet
    """)

  def test_base_class_with_typevar(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      T = TypeVar("T")
      class A(List[T]): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      T = TypeVar("T")
      class A(List[T]): ...
    """)

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
      U = TypeVar("U", bound=str)  # ok
      V = TypeVar("V", bound=int if __random__ else float)  # invalid-typevar
    """)

  def test_covariant(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", covariant=True)  # not-supported-yet
      S = TypeVar("S", covariant=42)  # invalid-typevar[e1]
      U = TypeVar("U", covariant=True if __random__ else False)  # invalid-typevar[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Expected.*bool.*Actual.*int", "e2": r"constant"})

  def test_contravariant(self):
    _, errors = self.InferWithErrors("""
      from typing import TypeVar
      T = TypeVar("T", contravariant=True)  # not-supported-yet
      S = TypeVar("S", contravariant=42)  # invalid-typevar[e1]
      U = TypeVar("U", contravariant=True if __random__ else False)  # invalid-typevar[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Expected.*bool.*Actual.*int", "e2": r"constant"})

  def test_dont_propagate_pyval(self):
    # in functions like f(x: T) -> T, if T has constraints we should not copy
    # the value of constant types between instances of the typevar.
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import TypeVar
        AnyInt = TypeVar('AnyInt', int)
        def f(x: AnyInt) -> AnyInt: ...
      """)
      ty = self.Infer("""
        import a
        if a.f(0):
          x = 3
        if a.f(1):
          y = 3
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
        y = ...  # type: int
      """)

  def test_property_type_param(self):
    # We should allow property signatures of the form f(self: T) -> X[T]
    # without complaining about the class not being parametrised over T
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List
      T = TypeVar('T')
      class A(object):
          @property
          def foo(self: T) -> List[T]: ...
      class B(A): ...
      """)
      ty = self.Infer("""
        import a
        x = a.A().foo
        y = a.B().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """)

  def test_property_type_param2(self):
    # Test for classes inheriting from Generic[X]
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[T]: ...
      class B(A, Generic[U]): ...
      def make_A() -> A[int]: ...
      def make_B() -> B[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
        y = a.make_B().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A[int]]
        y = ...  # type: List[a.B[int]]
      """)

  # Skipping due to b/66005735
  @test_base.skip("Type parameter bug")
  def test_property_type_param3(self):
    # Don't mix up the class parameter and the property parameter
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U')
      class A(Generic[U]):
          @property
          def foo(self: T) -> List[U]: ...
      def make_A() -> A[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: List[int]
      """)

  def test_property_type_param_with_constraints(self):
    # Test setting self to a constrained type
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Generic
      T = TypeVar('T')
      U = TypeVar('U', int, str)
      X = TypeVar('X', int)
      class A(Generic[U]):
          @property
          def foo(self: A[X]) -> List[X]: ...
      def make_A() -> A[int]: ...
      """)
      ty = self.Infer("""
        import a
        x = a.make_A().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        a = ...  # type: module
        x = ...  # type: List[int]
      """)

  def test_classmethod_type_param(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, List, Type
      T = TypeVar('T')
      class A(object):
          @classmethod
          def foo(self: Type[T]) -> List[T]: ...
      class B(A): ...
      """)
      ty = self.Infer("""
        import a
        v = a.A.foo()
        w = a.B.foo()
        x = a.A().foo()
        y = a.B().foo()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        v = ...  # type: List[a.A]
        w = ...  # type: List[a.B]
        x = ...  # type: List[a.A]
        y = ...  # type: List[a.B]
      """)

  def test_metaclass_property_type_param(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
      from typing import TypeVar, Type, List
      T = TypeVar('T')
      class Meta():
        @property
        def foo(self: Type[T]) -> List[T]: ...

      class A(metaclass=Meta):
        pass
      """)
      ty = self.Infer("""
        import a
        x = a.A.foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import List
        import a
        a = ...  # type: module
        x = ...  # type: List[a.A]
      """)

  def test_top_level_union(self):
    ty = self.Infer("""
      from typing import TypeVar
      if __random__:
        T = TypeVar("T")
      else:
        T = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      T = ...  # type: Any
    """)

  def test_store_typevar_in_dict(self):
    """Convert a typevar to Any when stored as a dict value."""
    # See abstract.Dict.setitem_slot for why this is needed.
    ty = self.Infer("""
      from typing import TypeVar
      T = TypeVar("T")
      a = {'key': T}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, TypeVar
      a = ...  # type: Dict[str, Any]
      T = TypeVar('T')
    """)

  def test_late_bound(self):
    _, errors = self.InferWithErrors("""
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
    self.assertErrorRegexes(errors, {
        "e1": r"mutually exclusive", "e2": r"empty string",
        "e3": r"Must be constant", "e4": r"Name.*Bar"})

  def test_late_constraints(self):
    ty = self.Infer("""
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", "int", "float")
      U = TypeVar("U", "List[int]", List[float])
      V = TypeVar("V", "Foo", "List[Foo]")
      class Foo:
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar
      S = TypeVar("S", int, float)
      T = TypeVar("T", int, float)
      U = TypeVar("U", List[int], List[float])
      V = TypeVar("V", Foo, List[Foo])
      class Foo:
        pass
    """)

  def test_typevar_in_alias(self):
    ty = self.Infer("""
      from typing import TypeVar, Union
      T = TypeVar("T", int, float)
      Num = Union[T, complex]
      x = 10  # type: Num[int]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar, Union
      T = TypeVar("T", int, float)
      Num: Any
      x: Union[int, complex] = ...
    """)

  def test_recursive_alias(self):
    errors = self.CheckWithErrors("""
      from typing import Any, Iterable, TypeVar, Union
      T = TypeVar("T")
      X = Union[Any, Iterable["X"]]  # not-supported-yet[e]
      Y = Union[Any, X]
    """)
    self.assertErrorRegexes(errors, {"e": r"Recursive.*X"})

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
      class Foo(object):
        def __init__(self):
          self.f1 = self.f2
        def f2(self, x):
          # type: (T) -> T
          return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, TypeVar
      T = TypeVar('T')
      class Foo:
        f1: Callable[[T], T]
        def __init__(self) -> None: ...
        def f2(self, x: T) -> T: ...
    """)


test_base.main(globals(), __name__ == "__main__")
