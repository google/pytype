"""Tests for the chex overlay."""

import contextlib

from pytype import file_utils
from pytype.tests import test_base


class TestDataclass(test_base.TargetPython3FeatureTest):
  """Tests for chex.dataclass."""

  @contextlib.contextmanager
  def _add_chex(self):
    with file_utils.Tempdir() as d:
      d.create_file("chex.pyi", """
        from typing import Any
        def dataclass(
            cls = ..., *, init = ..., repr = ..., eq = ..., order = ...,
            unsafe_hash = ..., frozen = ..., mappable_dataclass = ...,
            restricted_inheritance = ...) -> Any: ...
      """)
      yield d

  def Check(self, *args, **kwargs):
    with self._add_chex() as d:
      return super().Infer(*args, **kwargs, pythonpath=[d.path])

  def Infer(self, *args, **kwargs):
    with self._add_chex() as d:
      return super().Infer(*args, **kwargs, pythonpath=[d.path])

  def test_basic(self):
    ty = self.Infer("""
      import chex
      @chex.dataclass
      class Foo:
        x: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Mapping, TypeVar
      chex: module
      _T = TypeVar('_T', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        def __init__(self, x: int) -> None: ...
        def replace(self: _T, **changes) -> _T: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
    """)

  def test_not_mappable(self):
    ty = self.Infer("""
      import chex
      @chex.dataclass(mappable_dataclass=False)
      class Foo:
        x: int
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import TypeVar
      chex: module
      _T = TypeVar('_T', bound=Foo)
      @dataclasses.dataclass
      class Foo:
        x: int
        def __init__(self, x: int) -> None: ...
        def replace(self: _T, **changes) -> _T: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
    """)

  def test_use_mappable(self):
    self.Check("""
      import chex
      from typing import Sequence

      @chex.dataclass
      class Foo:
        x: int

      def f(foos: Sequence[Foo]):
        for foo in foos:
          yield foo["x"]
    """)

  def test_replace(self):
    ty = self.Infer("""
      import chex
      @chex.dataclass
      class Foo:
        x: int
      foo = Foo(0).replace(x=5)
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Mapping, TypeVar
      chex: module
      _T = TypeVar('_T', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        def __init__(self, x: int) -> None: ...
        def replace(self: _T, **changes) -> _T: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
      foo: Foo
    """)

  def test_from_tuple(self):
    ty = self.Infer("""
      import chex
      @chex.dataclass
      class Foo:
        x: int
      foo = Foo.from_tuple((0,))
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Mapping, TypeVar
      chex: module
      _T = TypeVar('_T', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        def __init__(self, x: int) -> None: ...
        def replace(self: _T, **changes) -> _T: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
      foo: Foo
    """)

  def test_to_tuple(self):
    ty = self.Infer("""
      import chex
      @chex.dataclass
      class Foo:
        x: int
      tup = Foo(0).to_tuple()
    """)
    self.assertTypesMatchPytd(ty, """
      import dataclasses
      from typing import Mapping, TypeVar
      chex: module
      _T = TypeVar('_T', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        def __init__(self, x: int) -> None: ...
        def replace(self: _T, **changes) -> _T: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
      tup: tuple
    """)


test_base.main(globals(), __name__ == "__main__")
