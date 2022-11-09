"""Tests for TypeGuard (PEP 647)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TypingExtensionsTest(test_base.BaseTest):
  """Tests for typing_extensions.TypeGuard."""

  def test_typing_extensions(self):
    self.CheckWithErrors("""
      from typing_extensions import TypeGuard  # not-supported-yet

      def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
        return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if is_str_list(val):
          assert_type(val, list[str])
    """)


@test_utils.skipBeforePy((3, 10), "New in 3.10")
class TypeGuardTest(test_base.BaseTest):
  """Tests for typing.TypeGuard."""

  def test_basic(self):
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet

      def is_str_list(val: list[object]) -> TypeGuard[list[str]]:
        return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_typed_dict(self):
    self.CheckWithErrors("""
      from typing import TypedDict, TypeGuard  # not-supported-yet

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

  def test_not_bool_subclass(self):
    self.CheckWithErrors("""
      from typing import Callable, TypeGuard  # not-supported-yet
      x: Callable[..., TypeGuard[int]]
      y: Callable[..., bool] = x  # annotation-type-mismatch
    """)

  def test_multiple_arguments(self):
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet

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
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet

      class Foo:
        def is_str_list(self, val: list[object]) -> TypeGuard[list[str]]:
          return all(isinstance(x, str) for x in val)

      def f(foo: Foo, val: list[object]):
        if foo.is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_classmethod(self):
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet

      class Foo:
        @classmethod
        def is_str_list(cls, val: list[object]) -> TypeGuard[list[str]]:
          return all(isinstance(x, str) for x in val)

      def f(val: list[object]):
        if Foo.is_str_list(val):
          assert_type(val, list[str])
    """)

  def test_repeat_calls(self):
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet
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
    self.CheckWithErrors("""
      from typing import TypeGuard  # not-supported-yet
      def is_int(x: object) -> TypeGuard[int]:
        return isinstance(x, int)
      def f(val):
        if is_int(val):
          assert_type(val, int)
        if is_int(val):
          assert_type(val, int)
    """)

  def test_generic(self):
    self.CheckWithErrors("""
      from typing import TypeGuard, TypeVar  # not-supported-yet

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
    self.CheckWithErrors("""
      from typing import TypeGuard, TypeVar  # not-supported-yet

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

  @test_base.skip("Not supported yet")
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

  @test_base.skip("Not supported yet")
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


if __name__ == "__main__":
  test_base.main()
