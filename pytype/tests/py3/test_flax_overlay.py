"""Tests for the flax overlay."""

from pytype import file_utils
from pytype.tests import test_base


class TestStructDataclass(test_base.TargetPython3FeatureTest):
  """Tests for flax.struct.dataclass."""

  def test_basic(self):
    with file_utils.Tempdir() as d:
      d.create_file("flax/struct.pyi", """
        from typing import Type
        def dataclass(_cls: Type[_T]) -> Type[_T]: ...
      """)
      ty = self.Infer("""
        import flax
        @flax.struct.dataclass
        class Foo(object):
          x: bool
          y: int
          z: str
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        flax: module
        class Foo(object):
          x: bool
          y: int
          z: str
          def __init__(self, x: bool, y: int, z: str) -> None: ...
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
      from typing import Any
      dataclasses: module
      def field(**kwargs) -> Any: ...
    """)


class TestLinenModule(test_base.TargetPython3FeatureTest):
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
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from flax import linen as nn
        class Foo(nn.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        import flax.linen.module
        nn: module
        class Foo(flax.linen.module.Module):
          x: bool
          y: int
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
      """)

  def test_unexported_constructor(self):
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from flax.linen import module
        class Foo(module.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="foo")
      self.assertTypesMatchPytd(ty, """
        import __builtin__
        import flax.linen.module
        module: __builtin__.module
        class Foo(flax.linen.module.Module):
          x: bool
          y: int
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
      """)

  def test_relative_import_from_package_module(self):
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from .module import Module
        class Foo(Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="flax.linen.foo")
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import flax.linen.module
        Module: Type[flax.linen.module.Module]
        class Foo(flax.linen.module.Module):
          x: bool
          y: int
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
      """)

  def test_parent_import_from_package_module(self):
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      ty = self.Infer("""
        from .. import linen
        class Foo(linen.Module):
          x: bool
          y: int = 10
        """, pythonpath=[d.path], module_name="flax.linen.foo")
      self.assertTypesMatchPytd(ty, """
        import flax.linen.module
        linen: module
        class Foo(flax.linen.module.Module):
          x: bool
          y: int
          def __init__(self, x: bool, y: int = ..., name: str = ..., parent = ...) -> None: ...
      """)

  def test_self_type(self):
    """Match self: f.l.module.Module even if imported as f.l.Module."""
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      self.Check("""
        from flax import linen
        class Foo(linen.Module):
          x: int
        a = Foo(10)
        b = a.make_rng("a")  # called on base class
      """, pythonpath=[d.path])

  def test_invalid_field(self):
    with file_utils.Tempdir() as d:
      self._setup_linen_pyi(d)
      errors = self.CheckWithErrors("""
        from flax import linen as nn
        class Foo(nn.Module):  # invalid-annotation[e]
          x: bool
          name: str
        """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"name.*implicitly"})


test_base.main(globals(), __name__ == "__main__")
