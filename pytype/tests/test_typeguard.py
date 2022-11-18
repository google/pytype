"""Tests for TypeGuard (PEP 647)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypingExtensionsTest(test_base.BaseTest):
  """Tests for typing_extensions.TypeGuard."""

  def test_typing_extensions(self):
    self.Check("""
      from typing_extensions import TypeGuard

      def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
        return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if is_str_list(val):
          assert_type(val, list[str])
    """)

  @test_utils.skipFromPy((3, 10), "3.9- must use typing_extensions")
  def test_unsupported_version(self):
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet
    """)


@test_utils.skipBeforePy((3, 10), "New in 3.10")
class MisuseTest(test_base.BaseTest):
  """Tests for misuse of typing.TypeGuard."""

  def test_bool_subclass(self):
    # While PEP 647 says that TypeGuard is not a subtype of bool
    # (https://peps.python.org/pep-0647/#typeguard-type), mypy treats it as
    # such, and typeshed has the same expectation. For example, inspect.pyi has:
    #   def getmembers(..., predicate: Callable[[Any], bool] | None): ...
    #   def isclass(object: object) -> TypeGuard[type[Any]]: ...
    # (https://github.com/python/typeshed/blob/main/stdlib/inspect.pyi), so we
    # need to treat TypeGuard as a subtype of bool for the common
    #   getmembers(..., isclass)
    # idiom to work.
    self.Check("""
      from typing import Callable, TypeGuard
      x: Callable[..., TypeGuard[int]]
      y: Callable[..., bool] = x
    """)

  def test_unparameterized(self):
    self.CheckWithErrors("""
      from typing import TypeGuard
      def f(x) -> TypeGuard:  # invalid-annotation
        return isinstance(x, int)
      def g(x):
        if f(x):
          assert_type(x, 'Any')
    """)

  def test_not_toplevel_return(self):
    self.CheckWithErrors("""
      from typing import TypeGuard
      def f(x: TypeGuard[int]):  # invalid-annotation
        pass
      def g() -> list[TypeGuard[int]]:  # invalid-annotation
        return []
    """)

  def test_not_enough_parameters(self):
    self.CheckWithErrors("""
      from typing import TypeGuard
      def f() -> TypeGuard[int]:  # invalid-function-definition
        return True
      def f(x=None) -> TypeGuard[int]:  # invalid-function-definition
        return True
    """)


class PyiTest(test_base.BaseTest):
  """Tests for TypeGuard in pyi files."""

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_infer(self):
    ty, _ = self.InferWithErrors("""
      from typing import TypeGuard
      def f(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeGuard
      def f(x: object) -> TypeGuard[int]: ...
    """)

  def test_infer_extension(self):
    ty, _ = self.InferWithErrors("""
      from typing_extensions import TypeGuard
      def f(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeGuard
      def f(x: object) -> TypeGuard[int]: ...
    """)

  def test_import(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeGuard
      def f(x: object) -> TypeGuard[int]: ...
    """)]):
      self.Check("""
        import foo
        def f(x: object):
          if foo.f(x):
            assert_type(x, int)
      """)

  def test_import_extension(self):
    with self.DepTree([("foo.pyi", """
      from typing_extensions import TypeGuard
      def f(x: object) -> TypeGuard[int]: ...
    """)]):
      self.Check("""
        import foo
        def f(x: object):
          if foo.f(x):
            assert_type(x, int)
      """)

  def test_generic(self):
    with self.DepTree([("foo.pyi", """
      from typing import Optional, TypeGuard, TypeVar
      T = TypeVar('T')
      def f(x: Optional[int]) -> TypeGuard[int]: ...
    """)]):
      self.Check("""
        import foo
        from typing import Optional
        def f(x: Optional[int]):
          if foo.f(x):
            assert_type(x, int)
      """)

  def test_non_variable(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeGuard
      def f(x) -> TypeGuard[int]: ...
    """)]):
      errors = self.CheckWithErrors("""
        import foo
        from typing import Dict
        def f(x: Dict[str, object]):
          print(foo.f(x['k']))  # not-supported-yet[e]
      """)
      self.assertErrorSequences(errors, {
          "e": ["TypeGuard function 'foo.f' with an arbitrary expression"]})


@test_utils.skipBeforePy((3, 10), "New in 3.10")
class CallableTest(test_base.BaseTest):
  """Tests for TypeGuard as a Callable return type."""

  def test_callable(self):
    self.Check("""
      from typing import Callable, TypeGuard
      def f(x: Callable[[object], TypeGuard[int]], y: object):
        if x(y):
          assert_type(y, int)
    """)

  def test_generic(self):
    self.Check("""
      from typing import Callable, TypeGuard, TypeVar
      T = TypeVar('T')
      def f(x: Callable[[T | None], TypeGuard[T]], y: int | None):
        if x(y):
          assert_type(y, int)
    """)

  def test_invalid(self):
    self.CheckWithErrors("""
      from typing import Any, Callable, List, TypeGuard
      x1: Callable[[], TypeGuard[int]]  # invalid-annotation
      x2: Callable[[TypeGuard[int]], Any]  # invalid-annotation
      x3: Callable[[object], List[TypeGuard[int]]]  # invalid-annotation
      x4: Callable[[object], TypeGuard]  # invalid-annotation
    """)

  def test_pyi(self):
    with self.DepTree([("foo.pyi", """
      from typing import Callable, TypeGuard
      f: Callable[[object], TypeGuard[int]]
    """)]):
      self.Check("""
        import foo
        def f(x: object):
          if foo.f(x):
            assert_type(x, int)
      """)

  def test_non_variable(self):
    errors = self.CheckWithErrors("""
      from typing import Callable, TypeGuard
      f: Callable[[object], TypeGuard[int]]
      def g(x: dict[str, object]):
        print(f(x['k']))  # not-supported-yet[e]
    """)
    self.assertErrorSequences(errors, {
        "e": "TypeGuard with an arbitrary expression"})


@test_utils.skipBeforePy((3, 10), "New in 3.10")
class TypeGuardTest(test_base.BaseTest):
  """Tests for typing.TypeGuard."""

  def test_basic(self):
    self.Check("""
      from typing import TypeGuard

      def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
        return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_typed_dict(self):
    self.Check("""
      from typing import TypedDict, TypeGuard

      class Person(TypedDict):
        name: str
        age: int

      def is_person(val: dict) -> TypeGuard[Person]:
        try:
          return isinstance(val["name"], str) and isinstance(val["age"], int)
        except KeyError:
          return False

      def f(val: dict):
        if is_person(val):
          assert_type(val, Person)
    """)

  def test_multiple_arguments(self):
    self.Check("""
      from typing import TypeGuard

      def is_str_list(
          val: list[object], allow_empty: bool) -> TypeGuard[list[str]]:
        if len(val) == 0:
          return allow_empty
        return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if is_str_list(val, allow_empty=False):
          assert_type(val, list[str])
    """)

  def test_instance_method(self):
    self.Check("""
      from typing import TypeGuard

      class Foo:
        def is_str_list(self, val: list[object]) -> TypeGuard[list[str]]:
          return all(isinstance(x, str) for x in val)

      def f(foo: Foo, val: list[object]):
        if foo.is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_classmethod(self):
    self.Check("""
      from typing import TypeGuard

      class Foo:
        @classmethod
        def is_str_list(cls, val: list[object]) -> TypeGuard[list[str]]:
          return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if Foo.is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_repeat_calls(self):
    self.Check("""
      from typing import TypeGuard
      def is_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
      def f(val):
        if is_int(val):
          assert_type(val, int)
      def g(val):
        if is_int(val):
          assert_type(val, int)
    """)

  def test_repeat_calls_same_function(self):
    self.Check("""
      from typing import TypeGuard
      def is_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
      def f(val):
        if is_int(val):
          assert_type(val, int)
        if is_int(val):
          assert_type(val, int)
    """)

  def test_generic(self):
    self.Check("""
      from typing import TypeGuard, TypeVar

      _T = TypeVar("_T")

      def is_two_element_tuple(val: tuple[_T, ...]) -> TypeGuard[tuple[_T, _T]]:
        return len(val) == 2

      def f(names: tuple[str, ...]):
        if is_two_element_tuple(names):
          assert_type(names, tuple[str, str])
        else:
          assert_type(names, tuple[str, ...])
    """)

  def test_union(self):
    self.Check("""
      from typing import TypeGuard, TypeVar

      _T = TypeVar("_T")

      def is_two_element_tuple(val: tuple[_T, ...]) -> TypeGuard[tuple[_T, _T]]:
        return len(val) == 2

      OneOrTwoStrs = tuple[str] | tuple[str, str]

      def f(val: OneOrTwoStrs):
        if is_two_element_tuple(val):
          assert_type(val, tuple[str, str])
        else:
          assert_type(val, OneOrTwoStrs)
        if not is_two_element_tuple(val):
          assert_type(val, OneOrTwoStrs)
        else:
          assert_type(val, tuple[str, str])
    """)

  def test_global(self):
    self.Check("""
      from typing import TypeGuard

      x: object

      def is_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)

      if is_int(x):
        assert_type(x, int)
      else:
        assert_type(x, object)
    """)

  def test_local(self):
    self.Check("""
      from typing import TypeGuard
      def is_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
      def f() -> object:
        return __any_object__
      def g():
        x = f()
        if is_int(x):
          assert_type(x, int)
        else:
          assert_type(x, object)
    """)

  def test_non_variable(self):
    errors = self.CheckWithErrors("""
      from typing import TypeGuard
      def f(x) -> TypeGuard[int]:
        return isinstance(x, int)
      def g(x: dict[str, object]):
        if f(x['k']):  # not-supported-yet[e]
          return x['k']
    """)
    self.assertErrorSequences(
        errors, {"e": ["TypeGuard function 'f' with an arbitrary expression"]})

  def test_cellvar(self):
    self.Check("""
      from typing import TypeGuard
      def f(x) -> TypeGuard[int]:
        return isinstance(x, int)
      def g_out(x, y):
        if f(y):
          assert_type(y, int)
        def g_in():
          print(x, y)  # use `x` and `y` here so they end up in co_cellvars
    """)

  def test_freevar(self):
    self.Check("""
      from typing import TypeGuard
      def f(x) -> TypeGuard[int]:
        return isinstance(x, int)
      def g_out(x, y):
        def g_in():
          print(x)  # use `x` here so both `x` and `y` end up in co_freevars
          if f(y):
            assert_type(y, int)
    """)

  def test_getattr(self):
    # Contrived example to make sure looking up the name of a builtin works.
    self.Check("""
      from typing import Any, Callable, TypeGuard
      def f(x) -> TypeGuard[Callable[[str], Any]]:
        return True
      def g():
        return f(getattr)
    """)


if __name__ == "__main__":
  test_base.main()
