"""Tests for the flax overlay."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class TestStructDataclass(test_base.BaseTest):
  """Tests for flax.struct.dataclass."""

  def _setup_struct_pyi(self, d):
    d.create_file("flax/struct.pyi", """
      from typing import Type
      def dataclass(_cls: Type[_T]) -> Type[_T]: ...
    """)

  def test_basic(self):
    with test_utils.Tempdir() as d:
      self._setup_struct_pyi(d)
      ty = self.Infer("""
        import flax
        @flax.struct.dataclass
        class Foo:
          x: bool
          y: int
          z: str
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        import flax
        from typing import Dict, TypeVar, Union

        _TFoo = TypeVar('_TFoo', bound=Foo)

        @dataclasses.dataclass
        class Foo:
          x: bool
          y: int
          z: str
          __dataclass_fields__: Dict[str, dataclasses.Field[Union[int, str]]]
          def __init__(self, x: bool, y: int, z: str) -> None: ...
          def replace(self: _TFoo, **kwargs) -> _TFoo: ...
      """)

  def test_redefine_field(self):
    # Tests that pytype can infer types for this (simplified) snippet of code
    # from flax.struct.py.
    ty = self.Infer("""
      import dataclasses
      def field(**kwargs):
        return dataclasses.field(**kwargs)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Any
      def field(**kwargs) -> Any: ...
    """)

  def test_replace(self):
    with test_utils.Tempdir() as d:
      self._setup_struct_pyi(d)
      self.Check("""
        import flax

        @flax.struct.dataclass
        class Foo:
          x: int = 10
          y: str = "hello"

        Foo().replace(y="a")
      """, pythonpath=[d.path])


class TestLinenModule(test_base.BaseTest):
  """Test dataclass construction in flax.linen.Module subclasses."""

  def _setup_linen_pyi(self, d):
    d.create_file("flax/linen/__init__.pyi", """
      from .module import Module
    """)
    d.create_file("flax/linen/module.pyi", """
      class Module:
        def make_rng(self, x: str) -> None: ...
    """)

  def test_constructor(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from flax import linen as nn
        class Foo(nn.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        from flax import linen as nn
        from typing import Dict, TypeVar
        _TFoo = TypeVar('_TFoo', bound=Foo)
        @dataclasses.dataclass
        class Foo(nn.module.Module):
          x: bool
          y: int
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
          def replace(self: _TFoo, **kwargs) -> _TFoo: ...
      """)

  def test_unexported_constructor(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from flax.linen import module
        class Foo(module.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        from flax.linen import module
        from typing import Dict, TypeVar
        _TFoo = TypeVar('_TFoo', bound=Foo)
        @dataclasses.dataclass
        class Foo(module.Module):
          x: bool
          y: int
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
          def replace(self: _TFoo, **kwargs) -> _TFoo: ...
      """)

  def test_relative_import_from_package_module(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from .module import Module
        class Foo(Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="flax.linen.foo")
      self.assertTypesMatchPytd(ty, """
        from typing import Dict, Type, TypeVar
        import flax.linen.module
        Module: Type[flax.linen.module.Module]
        _TFoo = TypeVar('_TFoo', bound=Foo)
        @dataclasses.dataclass
        class Foo(flax.linen.module.Module):
          x: bool
          y: int
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
          def replace(self: _TFoo, **kwargs) -> _TFoo: ...
      """)

  def test_parent_import_from_package_module(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from .. import linen
        class Foo(linen.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="flax.linen.foo")
      self.assertTypesMatchPytd(ty, """
        from flax import linen
        from typing import Dict, TypeVar
        _TFoo = TypeVar('_TFoo', bound=Foo)
        @dataclasses.dataclass
        class Foo(linen.module.Module):
          x: bool
          y: int
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
          def replace(self: _TFoo, **kwargs) -> _TFoo: ...
      """)

  def test_self_type(self):
    """Match self: f.l.module.Module even if imported as f.l.Module."""
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      self.Check("""
        from flax import linen
        class Foo(linen.Module):
          x: int
        a = Foo(10)
        b = a.make_rng("a")  # called on base class
      """, pythonpath=[d.path])

  def test_invalid_field(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      errors = self.CheckWithErrors("""
        from flax import linen as nn
        class Foo(nn.Module):  # invalid-annotation[e]
          x: bool
          name: str
        """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"name.*implicitly"})

  def test_setup(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      self.Check("""
        from flax import linen
        class Foo(linen.Module):
          x: int
          def setup(self):
            self.y = 10
        a = Foo(10)
        b = a.y
      """, pythonpath=[d.path])

  def test_reingest(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      foo_ty = self.Infer("""
        from flax import linen
        class Foo(linen.Module):
          pass
      """, pythonpath=[d.path])
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        class Bar(foo.Foo):
          x: int
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      import foo
      from typing import Any, Dict, TypeVar

      _TBar = TypeVar('_TBar', bound=Bar)
      @dataclasses.dataclass
      class Bar(foo.Foo):
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field]
        def __init__(
            self, x: int, name: str = ..., parent: Any = ...) -> None: ...
        def replace(self: _TBar, **kwargs) -> _TBar: ...
    """)

  def test_reingest_and_subclass(self):
    with test_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      foo_ty = self.Infer("""
        from flax import linen
        class Foo(linen.Module):
          pass
      """, pythonpath=[d.path])
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        class Bar(foo.Foo):
          pass
        class Baz(Bar):
          x: int
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import dataclasses
        import foo
        from typing import Any, Dict, TypeVar

        _TBar = TypeVar('_TBar', bound=Bar)
        @dataclasses.dataclass
        class Bar(foo.Foo):
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(self, name: str = ..., parent: Any = ...) -> None: ...
          def replace(self: _TBar, **kwargs) -> _TBar: ...

        _TBaz = TypeVar('_TBaz', bound=Baz)
        @dataclasses.dataclass
        class Baz(Bar):
          x: int
          __dataclass_fields__: Dict[str, dataclasses.Field]
          def __init__(
              self, x: int, name: str = ..., parent: Any = ...) -> None: ...
          def replace(self: _TBaz, **kwargs) -> _TBaz: ...
      """)


if __name__ == "__main__":
  test_base.main()
