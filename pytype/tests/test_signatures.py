"""Tests for matching against signatures."""

from pytype.tests import test_base


class SignatureTest(test_base.BaseTest):  # pylint: disable=missing-docstring

  def test_no_params(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self): ...
      def f1(): ...
      def f2(x: int): ...
      _: P = f1
      _: P = f2  # annotation-type-mismatch
    """)

  def test_params_are_contravariant(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: bool): ...
      def f1(x: int): ...
      def f2(x: bool): ...
      def f3(x: str): ...
      _: P = f1
      _: P = f2
      _: P = f3  # annotation-type-mismatch
    """)

  def test_return_type_is_covariant(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self) -> int: ...
      def f1() -> object: ...
      def f2() -> bool: return True
      _: P = f1  # annotation-type-mismatch
      _: P = f2
    """)

  # Each overload on the LHS must have at least one matching overload on
  # the RHS.

  def test_overloads1(self):
    self.CheckWithErrors("""
      from typing import Protocol, overload
      class P(Protocol):
        def __call__(self) -> int: ...
      @overload
      def f() -> int: ...
      @overload
      def f(x: int) -> float: ...
      _: P = f
    """)

  def test_overloads2(self):
    self.CheckWithErrors("""
      from typing import Protocol, overload
      class P(Protocol):
        @overload
        def __call__(self) -> int: ...
        @overload
        def __call__(self, x: bool) -> int: ...
        def __call__(self, *args, **kwargs): raise NotImplementedError

      @overload
      def f1() -> int: ...
      @overload
      def f1(x: int) -> bool: ...
      def f2(x: int) -> float: return 42.0

      _: P = f1
      _: P = f2  # annotation-type-mismatch
    """)

  # Cases involving different parameter kinds, all including positional-only
  # parameters.  For the tests with positive expectations we vary everything
  # that's significant (e.g., names, types).  For the tests with negative
  # expectations we avoid that so we can control what we're testing.

  def test_positional_only_optional_to_required(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int, /) -> object: ...
      def f(x: object, y: object = ..., /) -> int: return 42
      _: P = f
    """)

  def test_positional_only_required_to_optional(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int = 42, /) -> int: ...
      def f(x: int, y: int, /) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_positional_only_optional_to_none(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /) -> object: ...
      def f(x: object, y: object = ..., /) -> int: return 42
      _: P = f
    """)

  def test_positional_only_unexpected_argument(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int = 42, /) -> int: ...
      def f(x: int, /) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_positional_only_to_positional_keyword(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int, /) -> object: ...
      def f(x: object, /, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_positional_only_called_by_keyword(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, y: int = 42) -> int: ...
      def f(x: int, y: int, /) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_positional_keyword_optional_not_passed(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /) -> object: ...
      def f(x: object, /, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_positional_keyword_unexpected_argument(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, y: int = 42) -> int: ...
      def f(x: int, /) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_args_accepts_positional_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int, /) -> object: ...
      def f(x: object, /, *args: object) -> int: return 42
      _: P = f
    """)

  def test_args_not_required(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int = 42, /) -> object: ...
      def f(x: object, /, *args: object) -> int: return 42
      _: P = f
    """)

  def test_args_not_required_single_param(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /) -> object: ...
      def f(x: object, /, *args: object) -> int: return 42
      _: P = f
    """)

  def test_no_args_cant_accept_arbitrary_positional(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, *args: int) -> int: ...
      def f(x: int, y: int, /) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  def test_args_variance(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, *args: int) -> object: ...
      def f(x: object, /, *args: object) -> int: return 42
      _: P = f
    """)

  def test_args_variance_negative(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: object, /, *args: object) -> int: ...
      def f(x: int, /, *args: int) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  def test_args_with_extra_positional(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int, /, *args: int) -> object: ...
      def f(x: object, /, *args: object) -> int: return 42
      _: P = f
    """)

  # Dually for different parameter kinds, all including keyword-only
  # parameters.

  def test_keyword_only_optional_to_required(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, y: int, x: int) -> object: ...
      def f(*, x: object, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_keyword_only_required_to_optional(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int, y: int = 42) -> int: ...
      def f(*, x: int, y: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_keyword_only_optional_to_none(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int) -> object: ...
      def f(*, x: object, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_keyword_only_unexpected_argument(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int, y: int = 42) -> int: ...
      def f(*, x: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_keyword_only_to_positional_keyword(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, y: int, x: int) -> object: ...
      def f(x: object = ..., *, y: object) -> int: return 42
      _: P = f
    """)

  def test_keyword_only_called_positionally(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int = 42, *, y: int) -> int: ...
      def f(*, x: int, y: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_positional_keyword_to_keyword_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, y: int) -> object: ...
      def f(x: object = ..., *, y: object) -> int: return 42
      _: P = f
    """)

  def test_positional_keyword_unexpected_keyword_only(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int = 42, *, y: int) -> int: ...
      def f(*, x: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_kwargs_accepts_keyword_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int, y: int) -> object: ...
      def f(*, x: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_kwargs_accepts_optional_keyword_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int, y: int = 42) -> object: ...
      def f(x: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_kwargs_not_required(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int) -> object: ...
      def f(x: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_no_kwargs_cant_accept_arbitrary_keyword(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, *, x: int, **kwargs: int) -> int: ...
      def f(*, x: int, y: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_kwargs_variance(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, **kwargs: int) -> object: ...
      def f(x: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_kwargs_with_extra_keyword_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, *, y: int, **kwargs: int) -> object: ...
      def f(x: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_args_kwargs_variance(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, *args: int, **kwargs: int) -> object: ...
      def f(x: object, /, *args: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_args_kwargs_with_keyword_only(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, /, *args: int, y: int, **kwargs: int) -> object: ...
      def f(x: object, /, *args: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_kwargs_variance_negative(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: object, **kwargs: object) -> int: ...
      def f(x: int, **kwargs: int) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  def test_kwargs_with_keyword_only_variance_negative(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: object, **kwargs: object) -> int: ...
      def f(x: int, *, y: int, **kwargs: int) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  def test_args_kwargs_variance_negative(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: object, /, *args: object, **kwargs: object) -> int: ...
      def f(x: int, /, *args: int, **kwargs: int) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  def test_args_kwargs_keyword_only_variance_negative(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: object, /, *args: object, **kwargs: object) -> int: ...
      def f(x: int, /, *args: int, y: int, **kwargs: int) -> object: ...
      _: P = f  # annotation-type-mismatch
    """)

  # Cases involving only normal parameters.

  def test_normal_params_optional_to_required(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int) -> object: ...
      def f(x: object, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_normal_params_required_to_optional(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int = 42) -> int: ...
      def f(x: int, y: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_normal_params_optional_to_none(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int) -> object: ...
      def f(x: object, y: object = ...) -> int: return 42
      _: P = f
    """)

  def test_normal_params_unexpected_argument(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int = 42) -> int: ...
      def f(x: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_normal_params_with_args_kwargs(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int) -> object: ...
      def f(x: object, *args: object, **kwargs: object) -> int: return 42
      _: P = f
    """)

  def test_normal_params_with_args_mismatch(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int) -> int: ...
      def f(x: int, *args: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_normal_params_with_kwargs_mismatch(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int, y: int) -> int: ...
      def f(x: int, **kwargs: int) -> float: return 3.14
      _: P = f  # annotation-type-mismatch
    """)

  # Weird cases where a parameter in the supertype can be accepted by
  # either a positional-only or keyword-only parameter in the subtype.
  # Both have to be optional because not both will be passed.

  def test_weird_positional_or_keyword_both_optional(self):
    self.Check("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int) -> object: ...
      def f(y: object = ..., /, *, x: object = ...) -> int: return 42
      _: P = f
    """)

  def test_weird_positional_only_required(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int) -> int: ...
      def f(y: int, /, *, x: int = 42) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)

  def test_weird_keyword_only_required(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class P(Protocol):
        def __call__(self, x: int) -> int: ...
      def f(y: int = 42, /, *, x: int) -> int: return 42
      _: P = f  # annotation-type-mismatch
    """)


if __name__ == "__main__":
  test_base.main()
