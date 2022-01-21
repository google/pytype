"""Tests for typing.Final and typing.final."""

from pytype.tests import test_base


class TestFinalDecorator(test_base.BaseTest):
  """Test @final."""

  def test_subclass(self):
    err = self.CheckWithErrors("""
      from typing import final
      @final
      class A:
        pass
      class B(A):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_subclass_with_other_bases(self):
    err = self.CheckWithErrors("""
      from typing import final
      @final
      class A:
        pass
      class B(list, A):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_typing_extensions_import(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final
      class A:
        pass
      class B(A):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_override_method_in_base(self):
    err = self.CheckWithErrors("""
      from typing import final
      class A:
        @final
        def f(self):
          pass
      class B(A):  # final-error[e]
        def f(self):
          pass
    """)
    self.assertErrorSequences(
        err, {"e": ["Class B", "overrides", "final method f", "base class A"]})

  def test_override_method_in_mro(self):
    err = self.CheckWithErrors("""
      from typing import final
      class A:
        @final
        def f(self):
          pass
      class B(A):
        pass
      class C(B):  # final-error[e]
        def f(self):
          pass
    """)
    self.assertErrorSequences(
        err, {"e": ["Class C", "overrides", "final method f", "base class A"]})


class TestFinalDecoratorValidity(test_base.BaseTest):
  """Test whether @final is applicable in context."""

  def test_basic(self):
    self.Check("""
      from typing import final
      @final
      class A:
        @final
        def f(self):
          pass
    """)

  def test_decorators(self):
    self.Check("""
      from typing import final
      class A:
        @final
        @property
        def f(self):
          pass
        @final
        @classmethod
        def f(self):
          pass
        @final
        @staticmethod
        def f(self):
          pass
    """)

  def test_invalid(self):
    err = self.CheckWithErrors("""
      from typing import final
      @final  # final-error[e]
      def f(x):
        pass
    """)
    self.assertErrorSequences(err, {"e": ["Cannot apply @final", "f"]})


class TestFinal(test_base.BaseTest):
  """Test Final."""

  def test_reassign_with_same_type(self):
    err = self.CheckWithErrors("""
      from typing import Final
      x: Final[int] = 10
      x = 20  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_different_type(self):
    err = self.CheckWithErrors("""
      from typing import Final
      x: Final[int] = 10
      x = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_new_annotation(self):
    err = self.CheckWithErrors("""
      from typing import Final
      x: Final[int] = 10
      x: str = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_final(self):
    self.Check("""
      from typing import Final
      x: str = "20"
      x: Final[int] = 10
    """)

  def test_reassign_after_reassigning_with_final(self):
    err = self.CheckWithErrors("""
      from typing import Final
      x: str = "hello"
      x: Final[str] = "world"
      x = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_local_variable(self):
    err = self.CheckWithErrors("""
      from typing import Final
      def f():
        x: Final[int] = 10
        x: str = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_local_shadowing_global(self):
    self.Check("""
      from typing import Final
      x: Final[int] = 10
      def f():
        x: str = "20"
    """)

  @test_base.skip("Does not work with non-final annotations either")
  def test_modifying_global_within_function(self):
    err = self.CheckWithErrors("""
      from typing import Final
      x: Final[int] = 10
      def f():
        global x
        x = "20"  # annotation_type_mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_attribute(self):
    err = self.CheckWithErrors("""
      from typing import Final
      class A:
        def __init__(self):
          self.x: Final[int] = 10
        def f(self):
          self.x = 20  # final-error[e]
    """)
    self.assertErrorSequences(
        err, {"e": ["attribute", "x", "annotated with Final"]})

  def test_inference(self):
    self.CheckWithErrors("""
      from typing import Final
      x: Final = 10
      assert_type(x, int)
      x = 20  # final-error
    """)

  def test_override_attr_in_base(self):
    err = self.CheckWithErrors("""
      from typing import Final
      class A:
        FOO: Final[int] = 10
      class B(A):  # final-error[e]
        FOO = 20
    """)
    self.assertErrorSequences(
        err, {"e": ["Class B", "overrides", "final class attribute", "FOO",
                    "base class A"]})

  def test_override_attr_in_mro(self):
    err = self.CheckWithErrors("""
      from typing import Final
      class A:
        FOO: Final[int] = 10
      class B(A):
        pass
      class C(B):  # final-error[e]
        FOO = 20
    """)
    self.assertErrorSequences(
        err, {"e": ["Class C", "overrides", "final class attribute", "FOO",
                    "base class A"]})


if __name__ == "__main__":
  test_base.main()
