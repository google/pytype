"""Tests for overriding."""

from pytype.tests import test_base
from pytype.tests import test_utils


class OverridingTest(test_base.BaseTest):
  """Tests for overridden and overriding methods signature match."""

  # Positional-or-keyword -> positional-or-keyword, same name or underscore.
  def test_positional_or_keyword_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, b: str) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, b: str = "", c: int = 1, *, d: int = 2) -> None:
          pass
    """)

  def test_positional_or_keyword_underscore_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, _: str) -> None:
          pass

      class Bar(Foo):
        def f(self, _: int, b: str) -> None:
          pass
    """)

  # Positional-or-keyword -> positional-or-keyword, same name or underscore.
  def test_positional_or_keyword_name_mismatch(self):
    # We don't report it as an error, as this is a very common practice
    # in the absence of positional-only parameters.
    self.Check("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, b: int) -> None:
          pass
    """)

  # Positional-or-keyword -> positional-or-keyword, same name.
  def test_positional_or_keyword_to_keyword_only_mismatch(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, a: int) -> None:  # signature-mismatch[e]
          pass
    """)
    self.assertErrorSequences(
        errors, {
            "e": [
                "Overriding method signature mismatch",
                "Base signature: ",
                "Subclass signature: ",
                "Not enough positional parameters in overriding method.",
            ]
        })

  # Keyword-only -> Positional-or-keyword or keyword-only, same name
  def test_keyword_only_match(self):
    self.Check("""
      class Foo:
        def f(self, *, a: int, b: int, c: int = 0) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, *, b: int, c: int = 0, d: int = 1) -> None:
          pass
    """)

  # Keyword-only -> Positional-or-keyword or keyword-only, same name
  def test_keyword_only_name_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, b: int) -> None:  # signature-mismatch
          pass
    """)

  def test_keyword_only_name_mismatch_twice(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, a: int) -> None:
          pass

        def g(self, *, c: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, b: int) -> None:  # signature-mismatch
          pass

        def g(self, *, d: int) -> None:  # signature-mismatch
          pass
    """)

  # Keyword-only -> Positional-or-keyword or keyword-only, same name
  def test_keyword_only_count_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, a: int, b: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, a: int) -> None:  # signature-mismatch
          pass
    """)

  # Non-default -> non-default
  def test_default_to_non_default_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int = 0) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int) -> None:  # signature-mismatch
          pass
    """)

  # Default or missing -> default with the same value
  def test_default_to_default_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int = 0, *, c: int = 2) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int = 0, b: int = 1, * , c: int = 2, d: int = 3) -> None:
          pass
    """)

  # Default or missing -> default with the same value
  def test_keyword_default_value_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, t: int = 0) -> None:
          pass

      class Bar(Foo):
        def f(self, *, t: int = 1) -> None:  # signature-mismatch
          pass
  """)

  def test_partial_annotations(self):
    self.Check("""
      class Foo:
        def f(self, t, g: int) -> str:
          return ""

      class Bar(Foo):
        def f(self, t: int, g: int):
          pass
    """)

  def test_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, t: int) -> None:
          pass

      class Bar(Foo):
        def f(self, t: str) -> None:  # signature-mismatch
          pass
    """)

  def test_return_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self) -> int:
          return 0

      class Bar(Foo):
        def f(self) -> str:  # signature-mismatch
          return ''
    """)

  def test_none_return_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self) -> None:
          pass

      class Bar(Foo):
        def f(self) -> str:  # signature-mismatch
          return ''
    """)

  def test_return_type_matches_empty(self):
    with self.DepTree([("foo.py", """
      class Foo:
        def f(self):
          raise NotImplementedError()
    """)]):
      self.Check("""
        import foo
        class Bar(foo.Foo):
          def f(self) -> None:
            pass
      """)

  def test_pytdclass_signature_match(self):
    self.Check("""
      class Foo(list):
        def clear(self) -> None:
          pass
    """)

  def test_pytdclass_parameter_type_mismatch(self):
    errors = self.CheckWithErrors("""
      class Foo(list):
        def clear(self, x: int) -> None:  # signature-mismatch[e]
          pass
    """)
    self.assertErrorSequences(errors, {"e": ["list.clear(self)"]})

  def test_pytdclass_return_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo(list):
        def clear(self) -> str:  # signature-mismatch
          return ""
    """)

  def test_pytdclass_default_value_match(self):
    self.Check("""
      import unittest

      class A(unittest.case.TestCase):
        def assertDictEqual(self, d1, d2, msg=None):
          pass
    """)

  def test_pytdclass_default_value_mismatch(self):
    self.Check("""
      import unittest

      class A(unittest.case.TestCase):
        def assertDictEqual(self, d1, d2, msg=""):
          pass
    """)

  def test_subclass_subclass_signature_match(self):
    self.Check("""
      class Foo:
        def f(self, t: int) -> None:
          pass

      class Bar(Foo):
        pass

      class Baz(Bar):
        def f(self, t: int) -> None:
          pass
  """)

  def test_subclass_subclass_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, t: int) -> None:
          pass

      class Bar(Foo):
        pass

      class Baz(Bar):
        def f(self, t: str) -> None:  # signature-mismatch
          pass
  """)

  def test_keyword_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, t: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, t: str) -> None:  # signature-mismatch
          pass
  """)

  def test_keyword_to_positional_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, t: int) -> None:
          pass

      class Bar(Foo):
        def f(self, t: str) -> None:  # signature-mismatch
          pass
  """)

  def test_subclass_parameter_type_match(self):
    self.Check("""
      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t: B) -> None:
          pass

      class Bar(Foo):
        def f(self, t: A) -> None:
          pass
    """)

  def test_subclass_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t: A) -> None:
          pass

      class Bar(Foo):
        def f(self, t: B) -> None:  # signature-mismatch
          pass
    """)

  def test_subclass_return_type_match(self):
    self.Check("""
      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t) -> A:
          return A()

      class Bar(Foo):
        def f(self, t) -> B:
          return B()
    """)

  def test_subclass_return_type_mismatch(self):
    self.CheckWithErrors("""
      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t) -> B:
          return B()

      class Bar(Foo):
        def f(self, t) -> A:  # signature-mismatch
          return A()
    """)

  def test_multiple_inheritance_parameter_type_match(self):
    self.Check("""
      class A:
        pass

      class B(A):
        pass

      class C(A):
        pass

      class Foo:
        def f(self, t: B) -> None:
          pass

      class Bar:
        def f(self, t: C) -> None:
          pass

      class Baz(Foo, Bar):
        def f(self, t: A) -> None:
          pass
    """)

  def test_multiple_inheritance_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      class A:
        pass

      class B(A):
        pass

      class C(B):
        pass

      class Foo:
        def f(self, t: A) -> None:
          pass

      class Bar:
        def f(self, t: C) -> None:
          pass

      class Baz(Foo, Bar):
        def f(self, t: B) -> None:  # signature-mismatch
          pass
    """)

  def test_multiple_inheritance_return_type_match(self):
    self.Check("""
      class A:
        pass

      class B:
        pass

      class C(A, B):
        pass

      class Foo:
        def f(self, t) -> A:
          return A()

      class Bar:
        def f(self, t) -> B:
          return B()

      class Baz(Foo, Bar):
        def f(self, t) -> C:
          return C()
    """)

  def test_multiple_inheritance_return_type_mismatch(self):
    self.CheckWithErrors("""
      class A:
        pass

      class B(A):
        pass

      class C(B):
        pass

      class Foo:
        def f(self, t) -> A:
          return C()

      class Bar:
        def f(self, t) -> C:
          return C()

      class Baz(Foo, Bar):
        def f(self, t) -> B:  # signature-mismatch
          return C()
    """)

  # If the method is defined in several base classes, but not in the class
  # itself, then the first signature by MRO should match all other signatures.
  # Note that mismatch errors is reported on the class definition and not on
  # the method that triggers an error.
  def test_multiple_inheritance_base_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        pass

      class Baz:
        def f(self, a: int, b: int) -> None:
          pass

      class Qux(Bar, Baz):  # signature-mismatch
        pass
    """)

  def test_generic_type_match(self):
    self.Check("""
      from typing import Callable, Sequence

      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t: Callable[[A], B]) -> Sequence[Callable[[B], A]]:
          return []

      class Bar(Foo):
        def f(self, t: Callable[[B], A]) -> Sequence[Callable[[A], B]]:
          return []
    """)

  def test_covariant_generic_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      from typing import Sequence, Iterable

      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t: Iterable[A]) -> None:
          pass

      class Bar(Foo):
        def f(self, t: Iterable[B]) -> None:  # signature-mismatch
          pass
    """)

  def test_contravariant_generic_parameter_type_mismatch(self):
    self.CheckWithErrors("""
      from typing import Callable

      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t: Callable[[B], None]) -> None:
          pass

      class Bar(Foo):
        def f(self, t: Callable[[A], None]) -> None:  # signature-mismatch
          pass
    """)

  def test_covariant_generic_return_type_mismatch(self):
    self.CheckWithErrors("""
      from typing import Sequence

      class A:
        pass

      class B(A):
        pass

      class Foo:
        def f(self, t) -> Sequence[B]:
          return [B()]

      class Bar(Foo):
        def f(self, t) -> Sequence[A]:  # signature-mismatch
          return [A()]
    """)

  def test_subclass_of_generic_type_mismatch(self):
    # Note: we don't detect mismatch in type parameters yet.
    self.CheckWithErrors("""
      from typing import Generic, TypeVar

      T = TypeVar('T')

      class A(Generic[T]):
        def f(self, t: T) -> None:
          pass

        def g(self, t: int) -> None:
          pass

      class B(A[int]):
        def f(self, t: str) -> None:
          pass

        def g(self, t: str) -> None:  # signature-mismatch
          pass
    """)

  def test_varargs_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, b: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, *args: int) -> None:
          pass
    """)

  def test_varargs_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int, b: str) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, *args: int) -> None:  # signature-mismatch
          pass
    """)

  def test_varargs_count_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, *args: str) -> None:
          pass
    """)

  def test_pytd_varargs_not_annotated(self):
    with self.DepTree([("foo.py", """
        class Foo:
          def f(self, *args):
            pass
      """)]):
      self.Check("""
        import foo

        class Bar(foo.Foo):
          def f(self, x: int):
            pass
      """)

  def test_kwargs_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, *, b: int, c: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, **kwargs: int) -> None:
          pass
    """)

  def test_kwargs_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int, *, b: str) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, **kwargs: int) -> None:  # signature-mismatch
          pass
    """)

  def test_kwargs_count_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, *, b: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, *, b: int, **kwargs: str) -> None:
          pass
    """)

  def test_default_value_to_varargs(self):
    self.Check("""
      class Foo:
        def call(self, x: str, y: int = 0) -> None:
          pass

      class Bar(Foo):
        def call(self, x, *args) -> None:
          pass
    """)

  def test_default_value_to_kwargs(self):
    self.Check("""
      class Foo:
        def call(self, x: int, *, y: int, z: int = 0) -> None:
          pass

      class Bar(Foo):
        def call(self, x: int, **kwargs) -> None:
          pass
    """)

  def test_class_and_static_methods(self):
    self.Check("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar:
        @classmethod
        def f(cls, b: str) -> None:
          pass

      class Baz:
        @staticmethod
        def f(c: list) -> None:
          pass
    """)

  def test_self_name(self):
    self.Check("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        def f(this, self: int) -> None:
          pass
    """)

  def test_keyword_only_double_underscore_name_mismatch(self):
    # Names with two leading underscores are mangled by Python.
    # See https://peps.python.org/pep-0008/#method-names-and-instance-variables.
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, __a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, *, __a: int) -> None:  # signature-mismatch
          pass
    """)

  # Positional-only -> Positional-only or positional-or-keyword, any name.
  @test_utils.skipBeforePy((3, 8), "Positional-only supported in 3.8+")
  def test_positional_only_match(self):
    self.Check("""
      class Foo:
        def f(self, a: int, b: str, c: int = 0, /) -> None:
          pass

      class Bar(Foo):
        def f(self, d: int, / , e: str, f: int = 0, g: int = 1) -> None:
          pass
    """)

  # Positional-only -> Positional-only or positional-or-keyword, any name.
  @test_utils.skipBeforePy((3, 8), "Positional-only supported in 3.8+")
  def test_positional_only_to_keyword_only(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int, /) -> None:
          pass

      class Bar(Foo):
        def f(self, * , a: int) -> None:  # signature-mismatch
          pass
    """)

  # Positional-or-keyword -> positional-only.
  @test_utils.skipBeforePy((3, 8), "Positional-only supported in 3.8+")
  def test_positional_or_keyword_to_positional_only_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, /) -> None:  # signature-mismatch
          pass
    """)

  # Keyword-only -> Positional-or-keyword or keyword-only, same name.
  @test_utils.skipBeforePy((3, 8), "Positional-only supported in 3.8+")
  def test_keyword_only_to_positional_only_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, /) -> None:  # signature-mismatch
          pass
    """)

  # Keyword-only -> Positional-only, same name.
  @test_utils.skipBeforePy((3, 8), "Positional-only supported in 3.8+")
  def test_keyword_only_to_positional_only_count_mismatch(self):
    self.CheckWithErrors("""
      class Foo:
        def f(self, *, a: int) -> None:
          pass

      class Bar(Foo):
        def f(self, a: int, /) -> None:  # signature-mismatch
          pass
    """)

  def test_callable_multiple_inheritance(self):
    self.Check("""
      from typing import Callable
      class Foo:
        def __call__(self, x: int, *, y: str):
          pass
      class Bar(Callable, Foo):
        pass
    """)


if __name__ == "__main__":
  test_base.main()
