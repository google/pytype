"""Tests for TypeVar."""

from pytype import file_utils
from pytype.tests import test_base


class TypeVarTest(test_base.TargetPython3BasicTest):
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
      from typing import Any
      typing = ...  # type: module
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
    with file_utils.Tempdir() as d:
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

  def test_multiple_substitution(self):
    ty = self.Infer("""
      from typing import Dict, Tuple, TypeVar
      K = TypeVar("K")
      V = TypeVar("V")
      def f(x: Dict[K, V]) -> Tuple[V, K]:
        return __any_object__
      v = f({})
      w = f({"test": 42})
    """, deep=False)
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
    """, deep=False)
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
        "e1": r"List\[S\].*set", "e2": r"str.*int", "e3": r"bool.*int",
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
      class A(object): pass
      class B(object): pass
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      import types
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

      class Foo(object):
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
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Optional\[T\].*int"})

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
      import __future__
      from typing import Any
      typing = ...  # type: module
      unicode_literals = ...  # type: __future__._Feature
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
    # types inferred as Any due to b/123835298
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Generic, Any
      T = TypeVar('T')
      class A(Generic[T]):
          _foo: Any
          foo: Any
          def __init__(self, foo: T) -> None: ...
    """)

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
      from typing import Dict, List, TypeVar, Union, Any
      T = TypeVar("T")
      U = TypeVar("U")
      Foo: Any
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
    self.assertErrorRegexes(err, {"e": "Union.*2.*instantiated.*1"})

  def test_use_unsupported_typevar(self):
    # Test that we don't crash when using this pattern (b/162274390)
    self.CheckWithErrors("""
      from typing import List, TypeVar, Union
      T = TypeVar("T")
      Tree = Union[T, List['Tree']]  # not-supported-yet
      def f(x: Tree[int]): ... # no error since Tree is set to Any
    """)


class TypeVarTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for TypeVar in Python 3."""

  def test_use_constraints_from_pyi(self):
    with file_utils.Tempdir() as d:
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
      from typing import List
      subprocess: module
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


test_base.main(globals(), __name__ == "__main__")
