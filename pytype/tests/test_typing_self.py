"""Tests for typing.Self."""

import textwrap

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class SelfTest(test_base.BaseTest):
  """Tests for typing.Self."""

  def test_instance_method_return(self):
    self.Check("""
      from typing_extensions import Self
      class A:
        def f(self) -> Self:
          return self
      class B(A):
        pass
      assert_type(A().f(), A)
      assert_type(B().f(), B)
    """)

  def test_parameterized_return(self):
    self.Check("""
      from typing import List
      from typing_extensions import Self
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
      from typing_extensions import Self
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
    self.Check("""
      from typing_extensions import Self
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
    self.Check("""
      from typing import Self
      class A:
        def f(self) -> Self:
          return self
      class B(A):
        pass
      assert_type(A().f(), A)
      assert_type(B().f(), B)
    """)

  def test_classmethod(self):
    self.Check("""
      from typing_extensions import Self
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
    self.Check("""
      from typing_extensions import Self
      class A:
        def __new__(cls) -> Self:
          return super().__new__(cls)
      class B(A):
        pass
      assert_type(A(), A)
      assert_type(B(), B)
    """)

  def test_generic_class(self):
    self.Check("""
      from typing import Generic, TypeVar
      from typing_extensions import Self
      T = TypeVar('T')
      class A(Generic[T]):
        def copy(self) -> Self:
          return self
      class B(A[T]):
        pass
      assert_type(A[int]().copy(), A[int])
      assert_type(B[str]().copy(), B[str])
    """)

  def test_protocol(self):
    # From https://peps.python.org/pep-0673/#use-in-protocols:
    #   If a protocol uses `Self` in methods or attribute annotations, then a
    #   class `Foo` is considered compatible with the protocol if its
    #   corresponding methods and attribute annotations use either `Self` or
    #   `Foo` or any of `Foo`'s subclasses.
    self.CheckWithErrors("""
      from typing import Protocol, TypeVar
      from typing_extensions import Self
      T = TypeVar('T')
      class MyProtocol(Protocol[T]):
        def f(self) -> Self:
          return self
      class Ok1:
        def f(self) -> MyProtocol:
          return self
      class Ok2:
        def f(self) -> 'Ok2':
          return self
      class Ok3:
        def f(self) -> Self:
          return self
      class Bad:
        def f(self) -> int:
          return 0
      def f(x: MyProtocol[str]):
        pass
      f(Ok1())
      f(Ok2())
      f(Ok3())
      f(Bad())  # wrong-arg-types
    """)

  def test_protocol_classmethod(self):
    self.CheckWithErrors("""
      from typing import Protocol, TypeVar
      from typing_extensions import Self
      T = TypeVar('T')
      class MyProtocol(Protocol[T]):
        @classmethod
        def build(cls) -> Self:
          return cls()
      class Ok:
        @classmethod
        def build(cls) -> 'Ok':
          return cls()
      class Bad:
        @classmethod
        def build(cls) -> int:
          return 0
      def f(x: MyProtocol[str]):
        pass
      f(Ok())
      f(Bad())  # wrong-arg-types
    """)

  def test_signature_mismatch(self):
    self.CheckWithErrors("""
      from typing_extensions import Self
      class Foo:
        def f(self) -> Self:
          return self
      class Ok(Foo):
        def f(self) -> 'Ok':
          return self
      class Bad(Foo):
        def f(self) -> int:  # signature-mismatch
          return 0
    """)

  def test_class_attribute(self):
    self.Check("""
      from typing_extensions import Self
      class Foo:
        x: Self
      class Bar(Foo):
        pass
      assert_type(Foo.x, Foo)
      assert_type(Foo().x, Foo)
      assert_type(Bar.x, Bar)
      assert_type(Bar().x, Bar)
    """)

  def test_instance_attribute(self):
    self.Check("""
      from typing_extensions import Self
      class Foo:
        def __init__(self, x: Self):
          self.x = x
          self.y: Self = __any_object__
      class Bar(Foo):
        pass
      assert_type(Foo(__any_object__).x, Foo)
      assert_type(Foo(__any_object__).y, Foo)
      assert_type(Bar(__any_object__).x, Bar)
      assert_type(Bar(__any_object__).y, Bar)
    """)

  def test_cast(self):
    self.Check("""
      from typing import cast
      from typing_extensions import Self
      class Foo:
        def f(self):
          return cast(Self, __any_object__)
      class Bar(Foo):
        pass
      assert_type(Foo().f(), Foo)
      assert_type(Bar().f(), Bar)
    """)

  def test_generic_attribute(self):
    self.Check("""
      from typing import Generic, TypeVar
      from typing_extensions import Self
      T = TypeVar('T')
      class C(Generic[T]):
        x: Self
      class D(C[T]):
        pass
      assert_type(C[int].x, C[int])
      assert_type(C[int]().x, C[int])
      assert_type(D[str].x, D[str])
      assert_type(D[str]().x, D[str])
    """)

  def test_attribute_mismatch(self):
    self.CheckWithErrors("""
      from typing import Protocol
      from typing_extensions import Self
      class C(Protocol):
        x: Self
      class Ok:
        x: 'Ok'
      class Bad:
        x: int
      def f(c: C):
        pass
      f(Ok())
      f(Bad())  # wrong-arg-types
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

  def test_protocol(self):
    with self.DepTree([("foo.pyi", """
      from typing import Protocol, Self, TypeVar
      T = TypeVar('T')
      class MyProtocol(Protocol[T]):
        @classmethod
        def build(cls) -> Self: ...
    """)]):
      self.CheckWithErrors("""
        import foo
        class Ok:
          @classmethod
          def build(cls) -> 'Ok':
            return cls()
        class Bad:
          @classmethod
          def build(cls) -> int:
            return 0
        def f(x: foo.MyProtocol[str]):
          pass
        f(Ok())
        f(Bad())  # wrong-arg-types
      """)

  def test_signature_mismatch(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        def f(self) -> Self: ...
    """)]):
      self.CheckWithErrors("""
        import foo
        class Ok(foo.A):
          def f(self) -> 'Ok':
            return self
        class Bad(foo.A):
          def f(self) -> int:  # signature-mismatch
            return 0
      """)

  def test_attribute(self):
    with self.DepTree([("foo.pyi", """
      from typing import Self
      class A:
        x: Self
    """)]):
      self.Check("""
        import foo
        class B(foo.A):
          pass
        assert_type(foo.A.x, foo.A)
        assert_type(foo.A().x, foo.A)
        assert_type(B.x, B)
        assert_type(B().x, B)
      """)

  def test_generic_attribute(self):
    with self.DepTree([("foo.pyi", """
      from typing import Generic, Self, TypeVar
      T = TypeVar('T')
      class A(Generic[T]):
        x: Self
    """)]):
      self.Check("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        class B(foo.A[T]):
          pass
        assert_type(foo.A[str].x, foo.A[str])
        assert_type(foo.A[int]().x, foo.A[int])
        assert_type(B[int].x, B[int])
        assert_type(B[str]().x, B[str])
      """)

  def test_attribute_mismatch(self):
    with self.DepTree([("foo.pyi", """
      from typing import Protocol, Self
      class C(Protocol):
        x: Self
    """)]):
      self.CheckWithErrors("""
        import foo
        class Ok:
          x: 'Ok'
        class Bad:
          x: str
        def f(c: foo.C):
          pass
        f(Ok())
        f(Bad())  # wrong-arg-types
      """)


class SelfReingestTest(test_base.BaseTest):
  """Tests for outputting typing.Self to a stub and reading the stub back in."""

  def test_output(self):
    ty = self.Infer("""
      from typing_extensions import Self
      class A:
        def f(self) -> Self:
          return self
    """)
    # We do a string comparison because the pyi parser desugars Self, and we
    # want to ensure we're outputting the prettier original form.
    expected = textwrap.dedent("""\
      from typing import Self

      class A:
          def f(self) -> Self: ...""")
    actual = pytd_utils.Print(ty)
    self.assertMultiLineEqual(expected, actual)

  def test_attribute_output(self):
    ty = self.Infer("""
      from typing_extensions import Self
      class A:
        x: Self
        def __init__(self):
          self.y: Self = __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Self
      class A:
        x: Self
        y: Self
        def __init__(self) -> None: ...
    """)

  def test_instance_method_return(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self
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
      from typing_extensions import Self
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
      from typing_extensions import Self
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
      from typing_extensions import Self
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
      from typing import Self
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
      from typing_extensions import Self
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
      from typing_extensions import Self
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
      from typing_extensions import Self
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

  def test_protocol(self):
    with self.DepTree([("foo.py", """
      from typing import Protocol, TypeVar
      from typing_extensions import Self
      T = TypeVar('T')
      class MyProtocol(Protocol[T]):
        def f(self) -> Self:
          return self
    """)]):
      self.CheckWithErrors("""
        import foo
        from typing_extensions import Self
        class Ok:
          def f(self) -> Self:
            return self
        class Bad:
          def f(self) -> int:
            return 0
        def f(x: foo.MyProtocol[str]):
          pass
        f(Ok())
        f(Bad())  # wrong-arg-types
      """)

  def test_signature_mismatch(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Self
      class A:
        def f(self) -> Self:
          return self
    """)]):
      self.CheckWithErrors("""
        import foo
        class Ok(foo.A):
          def f(self) -> foo.A:
            return self
        class Bad(foo.A):
          def f(self) -> int:  # signature-mismatch
            return 0
      """)


class IllegalLocationTest(test_base.BaseTest):
  """Tests for typing.Self in illegal locations."""

  def test_function_annotation_not_in_class(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Self
      def f(x) -> Self:  # invalid-annotation[e]
        return x
    """)
    self.assertErrorSequences(
        errors, {"e": ["'typing.Self' outside of a class"]})

  def test_variable_annotation_not_in_class(self):
    errors = self.CheckWithErrors("""
      from typing_extensions import Self
      x: Self  # invalid-annotation[e1]
      y = ...  # type: Self  # invalid-annotation[e2]
    """)
    self.assertErrorSequences(errors, {"e1": ["'Self' not in scope"],
                                       "e2": ["'Self' not in scope"]})


if __name__ == "__main__":
  test_base.main()
