"""Tests for the @typing.dataclass_transform decorator."""

from pytype.tests import test_base


class TestDecorator(test_base.BaseTest):
  """Tests for the @dataclass_transform decorator."""

  def test_invalid_target(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform
      x = 10
      dataclass_transform()(x) # dataclass-error
    """)

  def test_args(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform
      dataclass_transform(eq_default=True)  # not-supported-yet
      def f(cls):
        return cls
    """)

  def test_pyi_args(self):
    # Args directly in a pyi file are silently ignored.
    with self.DepTree([("foo.pyi", """
      from typing import dataclass_transform

      @dataclass_transform(eq_default=True)
      def dc(cls): ...
    """)]):
      self.Check("""
        import foo

        @foo.dc
        class A:
          x: int

        a = A(x=10)
      """)


class TestFunction(test_base.BaseTest):
  """Tests for @dataclass_transform on functions."""

  def test_py_function(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform

      # NOTE: The decorator overrides the function body and makes `dc` a
      # dataclass decorator.
      @dataclass_transform()
      def dc(cls):
        return cls

      @dc
      class A:
        x: int

      a = A(x=10)
      assert_type(a, A)
    """)

  def test_write_pyi(self):
    ty, _ = self.InferWithErrors("""
      from typing_extensions import dataclass_transform

      @dataclass_transform(eq_default=True)  # not-supported-yet
      def dc(f):
        return f
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, dataclass_transform

      _T0 = TypeVar('_T0')

      @dataclass_transform
      def dc(f: _T0) -> _T0: ...
    """)

  def test_pyi_function(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar, dataclass_transform

      _T0 = TypeVar('_T0')

      @dataclass_transform
      def dc(cls: _T0) -> _T0: ...
    """)]):
      self.CheckWithErrors("""
        import foo

        @foo.dc
        class A:
          x: int

        a = A(x=10)
        b = A() # missing-parameter
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing import TypeVar
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      def dc(f):
        return f
    """)]):
      self.CheckWithErrors("""
        import foo

        @foo.dc
        class A:
          x: int

        a = A(x=10)
        b = A() # missing-parameter
      """)

  def test_function_with_arguments(self):
    self.Check("""
      from typing_extensions import dataclass_transform
      @dataclass_transform()
      def dc(cls, *, init=True, repr=True, eq=True, order=False,
             unsafe_hash=False, frozen=False, kw_only=False):
        return cls
    """)


class TestClass(test_base.BaseTest):
  """Tests for @dataclass_transform on classes."""

  def test_single_inheritance(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform
      @dataclass_transform()
      class Base: ...

      class A(Base):
          x: int
          y: str

      class B(A):
          z: int

      a = B(1, '2', 3)
      b = B(1, 2)  # missing-parameter
      c = B(1, 2, 3)  # wrong-arg-types
    """)

  def test_multiple_inheritance(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform
      @dataclass_transform()
      class Mixin: ...

      class Base:
        pass

      class A(Base, Mixin):
          x: int
          y: str

      class B(A):
          z: int

      a = B(1, '2', 3)
      b = B(1, 2)  # missing-parameter
      c = B(1, 2, 3)  # wrong-arg-types
    """)

  def test_redundant_decorator(self):
    self.CheckWithErrors("""
      import dataclasses
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class Base: ...

      @dataclasses.dataclass
      class A(Base):
          x: int
          y: str

      class B(A):
          z: int

      a = B(1, '2', 3)
      b = B(1, 2)  # missing-parameter
      c = B(1, 2, 3)  # wrong-arg-types
    """)

  def test_redundant_decorator_pyi(self):
    ty = self.Infer("""
      import dataclasses
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class A:
        pass

      @dataclasses.dataclass
      class B(A):
        x: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import dataclass_transform

      @dataclass_transform
      class A: ...

      @dataclasses.dataclass
      class B(A):
        x: int
        def __init__(self, x: int) -> None: ...
    """)

  def test_write_pyi(self):
    ty, _ = self.InferWithErrors("""
      from typing_extensions import dataclass_transform
      @dataclass_transform()
      class Mixin: ...

      class Base:
        pass

      class A(Base, Mixin):
          x: int
          y: str

      class B(A):
          z: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import dataclass_transform

      @dataclasses.dataclass
      class A(Base, Mixin):
          x: int
          y: str
          def __init__(self, x: int, y: str) -> None: ...

      @dataclasses.dataclass
      class B(A):
          z: int
          def __init__(self, x: int, y: str, z: int) -> None: ...

      class Base: ...

      @dataclass_transform
      class Mixin: ...
    """)

  def test_pyi_class(self):
    with self.DepTree([("foo.pyi", """
      from typing import dataclass_transform

      @dataclass_transform
      class Mixin:
        ...
    """)]):
      self.CheckWithErrors("""
        import foo

        class Base(foo.Mixin):
          x: int

        class A(Base):
          y: str

        a = A(x=10, y='foo')
        b = A(10) # missing-parameter
        c = A(10, 20) # wrong-arg-types
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class Mixin:
        pass
    """)]):
      self.CheckWithErrors("""
        import foo

        class Base(foo.Mixin):
          x: int

        class A(Base):
          y: str

        a = A(x=10, y='foo')
        b = A(10) # missing-parameter
        c = A(10, 20) # wrong-arg-types
      """)

  def test_init_subclass_impl(self):
    with self.DepTree([("foo.py", """
      import dataclasses
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class X:
        def __init_subclass__(cls):
          return dataclasses.dataclass(cls)
    """)]):
      self.CheckWithErrors("""
        import foo
        class Y(foo.X):
          x: int
        Y()  # missing-parameter
        Y(x=0)  # ok
        Y(x='')  # wrong-arg-types
      """)


class TestMetaclass(test_base.BaseTest):
  """Tests for @dataclass_transform on metaclasses."""

  def test_py_metaclass(self):
    self.CheckWithErrors("""
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class Meta(type): ...

      class Base(metaclass=Meta): ...

      class A(Base):
        x: int
        y: str

      a = A(1, '2')
      a = A(1, 2)  # wrong-arg-types
    """)

  def test_pyi_class(self):
    with self.DepTree([("foo.pyi", """
      from typing import dataclass_transform

      @dataclass_transform
      class Meta(type):
        ...

      class Base(metaclass=Meta): ...
    """)]):
      self.CheckWithErrors("""
        import foo

        class A(foo.Base):
          x: int
          y: str

        a = A(x=10, y='foo')
        b = A(10) # missing-parameter
        c = A(10, 20) # wrong-arg-types
      """)

  def test_reingest(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import dataclass_transform

      @dataclass_transform()
      class Meta(type):
        ...

      class Base(metaclass=Meta): ...
    """)]):
      self.CheckWithErrors("""
        import foo

        class A(foo.Base):
          x: int
          y: str

        a = A(x=10, y='foo')
        b = A(10) # missing-parameter
        c = A(10, 20) # wrong-arg-types
      """)


if __name__ == "__main__":
  test_base.main()
