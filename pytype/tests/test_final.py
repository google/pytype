"""Tests for typing.Final and typing.final."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestFinalDecorator(test_base.BaseTest):
  """Test @final."""

  def test_subclass(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final
      class A:
        pass
      class B(A):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_subclass_with_other_bases(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final
      class A:
        pass
      class B(list, A):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_override_method_in_base(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
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
      from typing_extensions import final
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

  def test_output_class(self):
    ty = self.Infer("""
      from typing_extensions import final
      @final
      class A:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import final
      @final
      class A: ...
    """)

  def test_output_method(self):
    ty = self.Infer("""
      from typing_extensions import final
      class A:
        @final
        def f(self):
          pass
        @final
        @classmethod
        def g(cls):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import final, Type
      class A:
        @final
        def f(self) -> None:
          pass
        @final
        @classmethod
        def g(cls: Type[A]) -> None:
          pass
    """)


class TestFinalDecoratorValidity(test_base.BaseTest):
  """Test whether @final is applicable in context."""

  def test_basic(self):
    self.Check("""
      from typing_extensions import final
      @final
      class A:
        @final
        def f(self):
          pass
    """)

  def test_decorators(self):
    self.Check("""
      from typing_extensions import final
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

  @test_utils.skipFromPy((3, 8), "MAKE_FUNCTION opcode lineno changed in 3.8")
  def test_invalid_pre38(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final  # final-error[e]
      def f(x):
        pass
    """)
    self.assertErrorSequences(err, {"e": ["Cannot apply @final", "f"]})

  @test_utils.skipBeforePy((3, 8), "MAKE_FUNCTION opcode lineno changed in 3.8")
  def test_invalid(self):
    err = self.CheckWithErrors("""
      from typing_extensions import final
      @final
      def f(x):  # final-error[e]
        pass
    """)
    self.assertErrorSequences(err, {"e": ["Cannot apply @final", "f"]})


class TestFinal(test_base.BaseTest):
  """Test Final."""

  def test_reassign_with_same_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      x: Final[int] = 10
      x = 20  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_different_type(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      x: Final[int] = 10
      x = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_new_annotation(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      x: Final[int] = 10
      x: str = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_reassign_with_final(self):
    self.Check("""
      from typing_extensions import Final
      x: str = "20"
      x: Final[int] = 10
    """)

  def test_reassign_after_reassigning_with_final(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      x: str = "hello"
      x: Final[str] = "world"
      x = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_local_variable(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      def f():
        x: Final[int] = 10
        x: str = "20"  # final-error[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_local_shadowing_global(self):
    self.Check("""
      from typing_extensions import Final
      x: Final[int] = 10
      def f():
        x: str = "20"
    """)

  @test_base.skip("Does not work with non-final annotations either")
  def test_modifying_global_within_function(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      x: Final[int] = 10
      def f():
        global x
        x = "20"  # annotation_type_mismatch[e]
    """)
    self.assertErrorSequences(err, {"e": ["x", "annotated with Final"]})

  def test_attribute(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      class A:
        def __init__(self):
          self.x: Final[int] = 10
        def f(self):
          self.x = 20  # final-error[e]
    """)
    self.assertErrorSequences(
        err, {"e": ["attribute", "x", "annotated with Final"]})

  def test_constructor(self):
    # Should not raise an error when analyzing __init__ multiple times.
    self.CheckWithErrors("""
      from typing_extensions import Final
      class A:
        def __init__(self, x: int):
          self.x: Final[int] = x
      b = A(10)
      c = A(20)
      assert_type(b.x, int)
      assert_type(c.x, int)
      b.x = 20  # final-error
    """)

  def test_inference(self):
    self.CheckWithErrors("""
      from typing_extensions import Final
      x: Final = 10
      assert_type(x, int)
      x = 20  # final-error
    """)

  def test_override_attr_in_base(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
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
      from typing_extensions import Final
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

  def test_cannot_use_in_signature(self):
    err = self.CheckWithErrors("""
      from typing_extensions import Final
      def f(x: Final[int]):  # final-error[e]
        pass
      def g(x: Final):  # final-error
        pass
      def h(x) -> Final[int]:  # final-error
        pass  # bad-return-type
      def i(x) -> Final:
        pass  # bad-return-type  # final-error
    """)
    self.assertErrorSequences(
        err, {"e": ["only be used", "assignments", "variable annotations"]})

  def test_cannot_use_in_type_params(self):
    self.CheckWithErrors("""
      from typing import List, Tuple
      from typing_extensions import Final
      x: List[Final[int]] = [10]  # invalid-annotation  # final-error
      y: Tuple[int, Final[int]] = (1, 2)  # invalid-annotation  # final-error
    """)

  def test_can_use_in_annotated(self):
    self.CheckWithErrors("""
      from typing import List
      from typing_extensions import Annotated, Final
      x: Annotated[Final[List[int]], 'valid'] = [10]
      y: Annotated[List[Final[int]], 'invalid'] = [10]  # invalid-annotation  # final-error
    """)

  def test_output_in_pyi(self):
    ty = self.Infer("""
      from typing_extensions import Final
      x: Final[int] = 10
      class A:
        y: Final[int] = 20
        def __init__(self):
          self.z: Final[int] = 30
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Final

      x: Final[int]

      class A:
          y: Final[int]
          z: Final[int]
          def __init__(self) -> None: ...
    """)


class TestFinalDecoratorInPyi(test_base.BaseTest):
  """Test @final in pyi files."""

  _FINAL_CLASS = """
    from typing import final
    @final
    class A: ...
  """

  _FINAL_METHOD = """
    from typing import final
    class A:
      @final
      def f(self):
        pass
  """

  def test_subclass(self):
    with self.DepTree([("foo.pyi", self._FINAL_CLASS)]):
      err = self.CheckWithErrors("""
        from foo import A
        class B(A):  # final-error[e]
          pass
      """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_subclass_with_other_bases(self):
    with self.DepTree([("foo.pyi", self._FINAL_CLASS)]):
      err = self.CheckWithErrors("""
        from foo import A
        class B(list, A):  # final-error[e]
          pass
      """)
    self.assertErrorSequences(err, {"e": ["final class", "A"]})

  def test_typing_extensions_import(self):
    foo = """
      from typing_extensions import final
      @final
      class A:
        pass
    """
    with self.DepTree([("foo.pyi", foo)]):
      self.CheckWithErrors("""
        from foo import A
        class B(A):  # final-error[e]
          pass
      """)

  def test_override_method_in_base(self):
    with self.DepTree([("foo.pyi", self._FINAL_METHOD)]):
      err = self.CheckWithErrors("""
        from foo import A
        class B(A):  # final-error[e]
          def f(self):
            pass
      """)
    self.assertErrorSequences(
        err, {"e": ["Class B", "overrides", "final method f", "base class A"]})

  def test_override_method_in_mro(self):
    with self.DepTree([("foo.pyi", self._FINAL_METHOD)]):
      self.CheckWithErrors("""
        from foo import A
        class B(A):
          pass
        class C(B):  # final-error[e]
          def f(self):
            pass
      """)


class TestFinalInPyi(test_base.BaseTest):
  """Test Final in pyi files."""

  _FINAL_ATTR = """
    from typing import Final
    class A:
      x: Final[int] = ...
  """

  def test_attribute(self):
    with self.DepTree([("foo.pyi", self._FINAL_ATTR)]):
      err = self.CheckWithErrors("""
        from foo import A
        a = A()
        a.x = 10  # final-error[e]
    """)
    self.assertErrorSequences(
        err, {"e": ["attribute", "x", "annotated with Final"]})

  def test_override_attr_in_base(self):
    with self.DepTree([("foo.pyi", self._FINAL_ATTR)]):
      err = self.CheckWithErrors("""
        from foo import A
        class B(A):  # final-error[e]
          x = 20
    """)
    self.assertErrorSequences(
        err, {"e": ["Class B", "overrides", "final class attribute", "x",
                    "base class A"]})

  def test_override_attr_in_mro(self):
    foo = """
      from typing import Final
      class A:
        x: Final[int] = ...
      class B(A):
        pass
    """
    with self.DepTree([("foo.pyi", foo)]):
      err = self.CheckWithErrors("""
        from foo import B
        class C(B):  # final-error[e]
          x = 20
      """)
    self.assertErrorSequences(
        err, {"e": ["Class C", "overrides", "final class attribute", "x",
                    "base class A"]})

  def test_match_assignment_against_annotation(self):
    foo = """
      from typing import Final
      k: Final[float] = ...
    """
    with self.DepTree([("foo.pyi", foo)]):
      err = self.CheckWithErrors("""
        from foo import k
        x: float = k
        y: str = k  # annotation-type-mismatch[e]
      """)
    self.assertErrorSequences(
        err, {"e": ["annotation for y", "str", "Final[float]"]})

  def test_attribute_access(self):
    foo = """
      from typing import Final, List
      k: Final[List[str]] = ...
    """
    with self.DepTree([("foo.pyi", foo)]):
      err = self.CheckWithErrors("""
        from foo import k
        a = k.count('a')
        b = k.random()  # attribute-error[e]
      """)
    self.assertErrorSequences(
        err, {"e": ["No attribute", "random", "Final[List[str]]"]})


if __name__ == "__main__":
  test_base.main()
