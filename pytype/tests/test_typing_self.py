"""Tests for typing.Self."""

from pytype.tests import test_base
from pytype.tests import test_utils


class SelfTest(test_base.BaseTest):
  """Tests for typing.Self."""

  def test_instance_method_return(self):
    self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet
      class A:
        def f(self) -> Self:
          return self
      class B(A):
        pass
      assert_type(A().f(), A)
      assert_type(B().f(), B)
    """)

  def test_parameterized_return(self):
    self.CheckWithErrors("""
      from typing import List
      from typing_extensions import Self  # not-supported-yet
      class A:
        def f(self) -> List[Self]:
          return [self]
      class B(A):
        pass
      assert_type(A().f(), "List[A]")
      assert_type(B().f(), "List[B]")
    """)

  def test_parameter(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet
      class A:
        def f(self, other: Self) -> bool:
          return False
      class B(A):
        pass
      B().f(B())  # ok
      B().f(0)  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["Expected", "B", "Actual", "int"]})

  def test_nested_class(self):
    self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet
      class A:
        class B:
          def f(self) -> Self:
            return self
      class C(A.B):
        pass
      assert_type(A.B().f(), A.B)
      assert_type(C().f(), C)
    """)

  @test_utils.skipBeforePy((3, 11), "typing.Self is new in 3.11")
  def test_import_from_typing(self):
    self.CheckWithErrors("""
      from typing import Self  # not-supported-yet
      class A:
        def f(self) -> Self:
          return self
      class B(A):
        pass
      assert_type(A().f(), A)
      assert_type(B().f(), B)
    """)

  def test_classmethod(self):
    self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet
      class A:
        @classmethod
        def build(cls) -> Self:
          return cls()
      class B(A):
        pass
      assert_type(A.build(), A)
      assert_type(B.build(), B)
    """)

  def test_new(self):
    self.CheckWithErrors("""
      from typing_extensions import Self  # not-supported-yet
      class A:
        def __new__(cls) -> Self:
          return super().__new__(cls)
      class B(A):
        pass
      assert_type(A(), A)
      assert_type(B(), B)
    """)

  def test_generic_class(self):
    self.CheckWithErrors("""
      from typing import Generic, TypeVar
      from typing_extensions import Self  # not-supported-yet
      T = TypeVar('T')
      class A(Generic[T]):
        def copy(self) -> Self:
          return self
      class B(A[T]):
        pass
      assert_type(A[int]().copy(), A[int])
      assert_type(B[str]().copy(), B[str])
    """)


class SelfPyiTest(test_base.BaseTest):
  """Tests for typing.Self usage in type stubs."""

  def test_instance_method_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), foo.A)
        assert_type(B().f(), B)
      """)

  def test_classmethod_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        @classmethod
        def f(cls) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A.f(), foo.A)
        assert_type(B.f(), B)
      """)

  def test_new_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def __new__(cls) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A(), foo.A)
        assert_type(B(), B)
      """)

  def test_parameterized_return(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self) -> list[Self]: ...
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), "List[foo.A]")
        assert_type(B().f(), "List[B]")
      """)

  def test_parameter(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self, other: Self) -> bool: ...
    """)]):
      errors = self.CheckWithErrors("""
        import foo
        class B(foo.A):
          pass
        B().f(B())  # ok
        B().f(0)  # wrong-arg-types[e]
      """)
      self.assertErrorSequences(
          errors, {"e": ["Expected", "B", "Actual", "int"]})

  def test_nested_class(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        class B:
          def f(self) -> Self: ...
    """)]):
      self.Check("""
        import foo
        class C(foo.A.B):
          pass
        assert_type(foo.A.B().f(), foo.A.B)
        assert_type(C().f(), C)
      """)

  def test_generic_class(self):
    with self.DepTree([("foo.pyi", """
      from typing import Generic, Self, TypeVar
      T = TypeVar('T')
      class A(Generic[T]):
        def copy(self) -> Self: ...
    """)]):
      self.Check("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        class B(foo.A[T]):
          pass
        assert_type(foo.A[int]().copy(), foo.A[int])
        assert_type(B[str]().copy(), B[str])
      """)


class SelfReingestTest(test_base.BaseTest):
  """Tests for outputting typing.Self to a stub and reading the stub back in."""

  def test_instance_method_return(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        def f(self) -> Self:
          return self
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), foo.A)
        assert_type(B().f(), B)
      """)

  def test_parameterized_return(self):
    with self.DepTree([("foo.py", """
      from typing import List
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        def f(self) -> List[Self]:
          return [self]
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), "List[foo.A]")
        assert_type(B().f(), "List[B]")
      """)

  def test_parameter(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        def f(self, other: Self) -> bool:
          return False
    """)]):
      errors = self.CheckWithErrors("""
        import foo
        class B(foo.A):
          pass
        B().f(B())  # ok
        B().f(0)  # wrong-arg-types[e]
      """)
      self.assertErrorSequences(
          errors, {"e": ["Expected", "B", "Actual", "int"]})

  def test_nested_class(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        class B:
          def f(self) -> Self:
            return self
    """)]):
      self.Check("""
        import foo
        class C(foo.A.B):
          pass
        assert_type(foo.A.B().f(), foo.A.B)
        assert_type(C().f(), C)
      """)

  @test_utils.skipBeforePy((3, 11), "typing.Self is new in 3.11")
  def test_import_from_typing(self):
    with self.DepTree([("foo.py", """
      from typing import Self  # pytype: disable=not-supported-yet
      class A:
        def f(self) -> Self:
          return self
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A().f(), foo.A)
        assert_type(B().f(), B)
      """)

  def test_classmethod(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        @classmethod
        def build(cls) -> Self:
          return cls()
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A.build(), foo.A)
        assert_type(B.build(), B)
      """)

  def test_new(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      class A:
        def __new__(cls) -> Self:
          return super().__new__(cls)
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A(), foo.A)
        assert_type(B(), B)
      """)

  def test_generic_class(self):
    with self.DepTree([("foo.py", """
      from typing import Generic, TypeVar
      from typing_extensions import Self  # pytype: disable=not-supported-yet
      T = TypeVar('T')
      class A(Generic[T]):
        def copy(self) -> Self:
          return self
    """)]):
      self.Check("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        class B(foo.A[T]):
          pass
        assert_type(foo.A[int]().copy(), foo.A[int])
        assert_type(B[str]().copy(), B[str])
      """)


if __name__ == "__main__":
  test_base.main()
