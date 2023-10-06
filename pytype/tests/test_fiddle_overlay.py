"""Tests for the fiddle overlay."""

from pytype.tests import test_base


_FIDDLE_PYI = """
from typing import Callable, Generic, Type, TypeVar, Union

T = TypeVar("T")

class Buildable(Generic[T], metaclass=abc.ABCMeta):
  def __init__(self, fn_or_cls: Union[Buildable, Type[T], Callable[..., T]], *args, **kwargs) -> None:
    self = Buildable[T]

class Config(Generic[T], Buildable[T]):
  ...

class Partial(Generic[T], Buildable[T]):
  def __call__(self, *args, **kwargs): ...
"""


class TestDataclassConfig(test_base.BaseTest):
  """Tests for Config wrapping a dataclass."""

  @property
  def buildable_type_name(self) -> str:
    return "Config"

  def test_basic(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        a = fiddle.{self.buildable_type_name}(Simple)
        a.x = 1
        a.y = 2  # annotation-type-mismatch
      """)

  def test_return_type(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        def f() -> fiddle.{self.buildable_type_name}[Simple]:
          a = fiddle.{self.buildable_type_name}(Simple)
          a.x = 1
          return a
      """)

  def test_pyi(self):
    with self.DepTree([
        ("fiddle.pyi", _FIDDLE_PYI),
        ("foo.pyi", f"""
            import dataclasses
            import fiddle

            @dataclasses.dataclass
            class Simple:
              x: int
              y: str

            a: fiddle.{self.buildable_type_name}[Simple]
         """)]):
      self.CheckWithErrors("""
        import foo
        a = foo.a
        a.x = 1
        a.y = 2  # annotation-type-mismatch
      """)

  def test_nested_dataclasses(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        @dataclasses.dataclass
        class Complex:
          x: Simple
          y: str

        a = fiddle.{self.buildable_type_name}(Complex)
        a.x.x = 1
        a.x.y = 2  # annotation-type-mismatch
      """)

  def test_frozen_dataclasses(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass(frozen=True)
        class Simple:
          x: int
          y: str

        @dataclasses.dataclass(frozen=True)
        class Complex:
          x: Simple
          y: str

        a = fiddle.{self.buildable_type_name}(Complex)
        a.x.x = 1
        a.x.y = 2  # annotation-type-mismatch
      """)

  def test_nested_constructor(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class DataClass:
          x: int
          y: str

        class RegularClass:
          def __init__(self, a, b):
            self.a = a
            self.b = b

        @dataclasses.dataclass
        class Parent:
          child_data: DataClass
          child_regular: RegularClass

        child_data = fiddle.Config(DataClass, x=1, y='y')
        child_regular = fiddle.Config(RegularClass, 1, 2)
        c = fiddle.{self.buildable_type_name}(Parent, child_data, child_regular)
      """)

  def test_nested_object_assignment(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class DataClass:
          x: int
          y: str

        class RegularClass:
          def __init__(self, a, b):
            self.a = a
            self.b = b

        @dataclasses.dataclass
        class Parent:
          child_data: DataClass
          child_regular: RegularClass

        c = fiddle.{self.buildable_type_name}(Parent)
        c.child_data = fiddle.Config(DataClass)
        c.child_data = DataClass(x=1, y='y')
        c.child_regular = fiddle.Config(RegularClass)
        c.child_regular = RegularClass(1, 2)
      """)

  def test_init_args(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        a = fiddle.{self.buildable_type_name}(Simple, x=1, y='2')
        b = fiddle.{self.buildable_type_name}(Simple, 1, '2')
        c = fiddle.{self.buildable_type_name}(Simple, 1, y='2')
        d = fiddle.{self.buildable_type_name}(Simple, x='a', y='2')  # wrong-arg-types
        e = fiddle.{self.buildable_type_name}(Simple, x=1)  # partial initialization is fine
        f = fiddle.{self.buildable_type_name}(Simple, x=1, z=3)  # wrong-keyword-args
        g = fiddle.{self.buildable_type_name}(Simple, 1, '2', 3)  # wrong-arg-count
      """)

  def test_pyi_underlying_class(self):
    with self.DepTree([
        ("fiddle.pyi", _FIDDLE_PYI),
        ("foo.pyi", """
        import dataclasses
        @dataclasses.dataclass
        class Simple:
          x: int
          y: str
         """),
    ]):
      self.CheckWithErrors(f"""
        import fiddle
        from foo import Simple

        a = fiddle.{self.buildable_type_name}(Simple, x=1, y='2')
        b = fiddle.{self.buildable_type_name}(Simple, 1, '2')
        c = fiddle.{self.buildable_type_name}(Simple, 1, y='2')
        d = fiddle.{self.buildable_type_name}(Simple, x='a', y='2')  # wrong-arg-types
        e = fiddle.{self.buildable_type_name}(Simple, x=1)  # partial initialization is fine
        f = fiddle.{self.buildable_type_name}(Simple, x=1, z=3)  # wrong-keyword-args
        g = fiddle.{self.buildable_type_name}(Simple, 1, '2', 3)  # wrong-arg-count
      """)

  def test_explicit_init(self):
    with self.DepTree([
        ("fiddle.pyi", _FIDDLE_PYI),
        ("foo.pyi", """
        import dataclasses
        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

          def __init__(self: Simple, x: int, y: str): ...
         """),
    ]):
      self.CheckWithErrors(f"""
        import fiddle
        from foo import Simple
        a = fiddle.{self.buildable_type_name}(Simple, x=1, y='2')
        b = fiddle.{self.buildable_type_name}(Simple, 1, '2')
        c = fiddle.{self.buildable_type_name}(Simple, 1, y='2')
        d = fiddle.{self.buildable_type_name}(Simple, x='a', y='2')  # wrong-arg-types
        e = fiddle.{self.buildable_type_name}(Simple, x=1)  # partial initialization is fine
        f = fiddle.{self.buildable_type_name}(Simple, x=1, z=3)  # wrong-keyword-args
        g = fiddle.{self.buildable_type_name}(Simple, 1, '2', 3)  # wrong-arg-count
      """)

  def test_typevar(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle
        from typing import TypeVar

        _T = TypeVar('_T')

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        def passthrough(conf: fiddle.{self.buildable_type_name}[_T]) -> fiddle.{self.buildable_type_name}[_T]:
          return conf

        a = fiddle.{self.buildable_type_name}(Simple)
        x = passthrough(a)
        assert_type(x, fiddle.{self.buildable_type_name}[Simple])
    """)

  def test_pyi_typevar(self):
    with self.DepTree([
        ("fiddle.pyi", _FIDDLE_PYI),
        ("foo.pyi", f"""
          import fiddle
          from typing import TypeVar

          _T = TypeVar('_T')

          def build(buildable: fiddle.{self.buildable_type_name}[_T]) -> _T: ...
         """),
    ]):
      self.Check(f"""
        import dataclasses
        import fiddle
        import foo

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        a = fiddle.{self.buildable_type_name}(Simple, x=1, y='2')
        b = foo.build(a)
        assert_type(b, Simple)
      """)

  def test_bare_type(self):
    """Check that we can match fiddle.Config against fiddle.Config[A]."""

    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check(f"""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class Simple:
          x: int
          y: str

        def f() -> fiddle.{self.buildable_type_name}:
          a = fiddle.{self.buildable_type_name}(Simple)
          a.x = 1
          return a
      """)

  def test_generic_dataclass(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        from typing import Generic, TypeVar
        import dataclasses
        import fiddle

        T = TypeVar('T')

        @dataclasses.dataclass
        class D(Generic[T]):
          x: T

        a = fiddle.{self.buildable_type_name}(D)
        a.x = 1
        b = fiddle.{self.buildable_type_name}(D[int])
        b.x = 1
        c = fiddle.{self.buildable_type_name}(D[str])
        c.x = 1  # annotation-type-mismatch
      """)

  def test_dataclass_error_detection(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors(f"""
        import dataclasses
        import fiddle
        @dataclasses.dataclass
        class A:
          x: int
          y: str
        A(x=0)  # missing-parameter
        fiddle.{self.buildable_type_name}(A, x=0)
        A(x=0)  # missing-parameter
      """)

  def test_dataclass_error_detection_pyi(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI), ("foo.pyi", """
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: int
        y: str
        def __init__(self, x: int, y: str) -> None: ...
    """)]):
      self.CheckWithErrors(f"""
        import fiddle
        import foo
        foo.Foo(x=0)  # missing-parameter
        fiddle.{self.buildable_type_name}(foo.Foo, x=0)
        foo.Foo(x=0)  # missing-parameter
      """)

  def test_imported_dataclass(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI), ("foo.pyi", """
      import dataclasses
      @dataclasses.dataclass
      class Foo:
        x: int
        y: str
        def __init__(self, x: int, y: str) -> None: ...
    """)]):
      errors = self.CheckWithErrors(f"""
        import fiddle
        import foo
        fiddle.{self.buildable_type_name}(foo.Foo, x='')  # wrong-arg-types[e]
      """)
      self.assertErrorSequences(errors, {"e": ["Expected", "x: int",
                                               "Actual", "x: str"]})


class TestDataclassPartial(TestDataclassConfig):
  """Test fiddle.Partial over dataclasses."""

  @property
  def buildable_type_name(self) -> str:
    return "Partial"

  def test_nested_partial_assignment(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import dataclasses
        import fiddle
        from typing import Callable

        @dataclasses.dataclass
        class DataClass:
          x: int
          y: str

        class RegularClass:
          def __init__(self, a, b):
            self.a = a
            self.b = b

        @dataclasses.dataclass
        class Parent:
          data_factory: Callable[..., DataClass]
          regular_factory: Callable[..., RegularClass]

        def data_builder(x: int = 1) -> DataClass:
          return DataClass(x=x, y='y')

        def regular_builder() -> RegularClass:
          return RegularClass(1, 2)

        c = fiddle.Partial(Parent)
        c.child_data = data_builder
        c.child_data = fiddle.Partial(DataClass)
        c.regular_factory = regular_builder
        c.regular_factory = fiddle.Partial(RegularClass)
      """)

  def test_config_partial_mismatch(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.CheckWithErrors("""
        import dataclasses
        import fiddle

        @dataclasses.dataclass
        class DataClass:
          x: int
          y: str

        def f() -> fiddle.Config:
          return fiddle.Partial(DataClass)  # bad-return-type
      """)


class TestClassConfig(test_base.BaseTest):
  """Tests for Config wrapping a regular python class."""

  def test_basic(self):
    # Config values wrapping non-dataclasses are currently treated as Any
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import fiddle

        class Simple:
          x: int
          y: str

        a = fiddle.Config(Simple)
        a.x = 1
        a.y = 2
      """)

  def test_init_args(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import fiddle

        class Simple:
          x: int
          y: str

        a = fiddle.Config(Simple, 1)
        b = fiddle.Config(Simple, 1, 2)  # no type checking yet
      """)


class TestFunctionConfig(test_base.BaseTest):
  """Tests for Config wrapping a function."""

  def test_basic(self):
    # Config values wrapping non-dataclasses are currently treated as Any
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import fiddle

        def Simple(x: int, y: str):
          pass

        a = fiddle.Config(Simple)
        a.x = 1
        a.y = 2
      """)

  def test_init_args(self):
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import fiddle

        def Simple(x: int, y: str):
          pass

        a = fiddle.Config(Simple, 1)
        b = fiddle.Config(Simple, 1, 2)  # no type checking yet
        b = fiddle.Config(Simple, 1, 2, 3)  # no arg checking yet
      """)

  def test_matching(self):
    # We should still recognise the Config class even if we currently treat it
    # as Config[Any]
    with self.DepTree([("fiddle.pyi", _FIDDLE_PYI)]):
      self.Check("""
        import fiddle

        def Simple(x: int, y: str):
          pass

        def f() -> fiddle.Config[Simple]:
          return fiddle.Config(Simple, 1)
      """)


if __name__ == "__main__":
  test_base.main()
