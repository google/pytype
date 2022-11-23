"""Tests for handling PYI code."""

from pytype.tests import test_base
from pytype.tests import test_utils


class PYITest(test_base.BaseTest):
  """Tests for PYI."""

  def test_unneccessary_any_import(self):
    ty = self.Infer("""
        import typing
        def foo(**kwargs: typing.Any) -> int: return 1
        def bar(*args: typing.Any) -> int: return 2
        """)
    self.assertTypesMatchPytd(ty, """
        import typing
        def foo(**kwargs) -> int: ...
        def bar(*args) -> int: ...
        """)

  def test_static_method_from_pyi_as_callable(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A:
          @staticmethod
          def callback(msg: str) -> None: ...
      """)
      self.Check("""
        from typing import Any, Callable
        import foo
        def func(c: Callable[[Any], None], arg: Any) -> None:
          c(arg)
        func(foo.A.callback, 'hello, world')
      """, pythonpath=[d.path])

  def test_class_method_from_pyi_as_callable(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A:
          @classmethod
          def callback(cls, msg: str) -> None: ...
      """)
      self.Check("""
        from typing import Any, Callable
        import foo
        def func(c: Callable[[Any], None], arg: Any) -> None:
          c(arg)
        func(foo.A.callback, 'hello, world')
      """, pythonpath=[d.path])

  def test_ellipsis(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: Ellipsis) -> None: ...
      """)
      self.CheckWithErrors("""
        import foo
        x = foo.f(...)
        y = foo.f(1)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_resolve_nested_type(self):
    with test_utils.Tempdir() as d:
      d.create_file("meta.pyi", """
        class Meta(type): ...
      """)
      d.create_file("foo.pyi", """
        import meta
        class Foo:
          class Bar(int, metaclass=meta.Meta): ...
          CONST: Foo.Bar
      """)
      self.Check("""
        import foo
        print(foo.Foo.CONST)
      """, pythonpath=[d.path])

  def test_partial_forward_reference(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        X1 = list['Y']
        X2 = list['Z[str]']
        X3 = int | 'Z[int]'
        Y = int
        T = TypeVar('T')
        class Z(Generic[T]): ...
      """)
      self.Check("""
        import foo
        assert_type(foo.X1, "Type[List[int]]")
        assert_type(foo.X2, "Type[List[foo.Z[str]]]")
        assert_type(foo.X3, "Type[Union[foo.Z[int], int]]")
      """, pythonpath=[d.path])

  def test_bare_callable(self):
    with self.DepTree([("foo.pyi", """
      import types
      def f(x) -> types.FunctionType: ...
    """)]):
      ty = self.Infer("""
        import foo
        def f(x):
          return foo.f(x)
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import Callable
      def f(x) -> Callable[..., nothing]: ...
    """)


class PYITestPython3Feature(test_base.BaseTest):
  """Tests for PYI."""

  def test_bytes(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f() -> bytes: ...
      """)
      ty = self.Infer("""
        import foo
        x = foo.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        x = ...  # type: bytes
      """)

  def test_imported_literal_alias(self):
    with self.DepTree([("foo.pyi", """
      from typing import Literal
      X = Literal["a", "b"]
    """), ("bar.pyi", """
      import foo
      from typing import Literal
      Y = Literal[foo.X, "c", "d"]
    """)]):
      self.Check("""
        import bar
        assert_type(bar.Y, "Type[Literal['a', 'b', 'c', 'd']]")
      """)

  def test_literal_in_dataclass(self):
    self.options.tweak(use_enum_overlay=False)
    with self.DepTree([("foo.pyi", """
      import enum
      class Base: ...
      class Foo(Base, enum.Enum):
        FOO = 'FOO'
    """), ("bar.pyi", """
      import dataclasses
      import foo
      from typing import Literal, Optional
      @dataclasses.dataclass
      class Bar(foo.Base):
        bar: Optional[Literal[foo.Foo.FOO]]
    """)]):
      self.Check("""
        import bar
        import dataclasses
        import foo
        @dataclasses.dataclass
        class Baz(foo.Base):
          baz: bar.Bar
      """)

  def test_literal_quotes(self):
    with self.DepTree([("foo.py", """
      from typing_extensions import Literal
      def f(x: Literal['"', "'"]):
        pass
    """)]):
      self.CheckWithErrors("""
        import foo
        foo.f('"')
        foo.f("'")
        foo.f('oops')  # wrong-arg-types
      """)


class PYITestAnnotated(test_base.BaseTest):
  """Tests for typing.Annotated."""

  @test_base.skip("We do not round-trip Annotated yet")
  def test_dict(self):
    ty = self.Infer("""
      from typing import Annotated
      x: Annotated[int, 'str', {'x': 1, 'y': 'z'}]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Annotated
      x: Annotated[int, 'str', {'x': 1, 'y': 'z'}]
    """)

  def test_invalid_pytype_metadata(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Annotated
        x: Annotated[int, "pytype_metadata", 2]
      """)
      err = self.CheckWithErrors("""
        import foo
        a = foo.x  # invalid-annotation[e]
      """, pythonpath=[d.path])
      self.assertErrorSequences(err, {"e": ["pytype_metadata"]})


class PYITestAll(test_base.BaseTest):
  """Tests for __all__."""

  def test_star_import(self):
    with self.DepTree([("foo.pyi", """
      import datetime
      __all__ = ['f', 'g']
      def f(x): ...
      def h(x): ...
    """), ("bar.pyi", """
      from foo import *
    """)]):
      self.CheckWithErrors("""
        import bar
        a = bar.datetime  # module-attr
        b = bar.f(1)
        c = bar.h(1)  # module-attr
      """)

  def test_http_client(self):
    """Check that we can get unexported symbols from http.client."""
    self.Check("""
      from http import client
      from six.moves import http_client
      status = http_client.FOUND or client.FOUND
    """)


if __name__ == "__main__":
  test_base.main()
