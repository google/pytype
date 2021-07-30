"""Tests for the chex overlay."""

import contextlib

from pytype import file_utils
from pytype.pytd import pytd_utils
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
    if "pythonpath" in kwargs:
      return super().Check(*args, **kwargs)
    else:
      with self._add_chex() as d:
        return super().Check(*args, **kwargs, pythonpath=[d.path])

  def Infer(self, *args, **kwargs):
    if "pythonpath" in kwargs:
      return super().Infer(*args, **kwargs)
    else:
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
      from typing import Dict, Mapping, TypeVar
      chex: module
      _TFoo = TypeVar('_TFoo', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field[int]]
        def __init__(self, x: int) -> None: ...
        def replace(self: _TFoo, **changes) -> _TFoo: ...
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
      from typing import Dict, TypeVar
      chex: module
      _TFoo = TypeVar('_TFoo', bound=Foo)
      @dataclasses.dataclass
      class Foo:
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field[int]]
        def __init__(self, x: int) -> None: ...
        def replace(self: _TFoo, **changes) -> _TFoo: ...
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
      from typing import Dict, Mapping, TypeVar
      chex: module
      _TFoo = TypeVar('_TFoo', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field[int]]
        def __init__(self, x: int) -> None: ...
        def replace(self: _TFoo, **changes) -> _TFoo: ...
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
      from typing import Dict, Mapping, TypeVar
      chex: module
      _TFoo = TypeVar('_TFoo', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field[int]]
        def __init__(self, x: int) -> None: ...
        def replace(self: _TFoo, **changes) -> _TFoo: ...
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
      from typing import Dict, Mapping, TypeVar
      chex: module
      _TFoo = TypeVar('_TFoo', bound=Foo)
      @dataclasses.dataclass
      class Foo(Mapping, object):
        x: int
        __dataclass_fields__: Dict[str, dataclasses.Field[int]]
        def __init__(self, x: int) -> None: ...
        def replace(self: _TFoo, **changes) -> _TFoo: ...
        @staticmethod
        def from_tuple(args) -> Foo: ...
        def to_tuple(self) -> tuple: ...
      tup: tuple
    """)

  def test_multiple_dataclasses(self):
    foo = self.Infer("""
      import chex
      @chex.dataclass
      class A:
        x: int
      @chex.dataclass
      class B:
        x: str
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        print(foo.B(x='hello').replace(x='world'))
      """, pythonpath=[d.path])

  def test_generic_dataclass(self):
    foo = self.Infer("""
      from typing import Generic, TypeVar
      import chex
      T = TypeVar("T")
      @chex.dataclass
      class A(Generic[T]):
        x: T
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo))
      self.Check("""
        import foo
        a = foo.A(x=42)
        assert_type(a.x, int)
      """, pythonpath=[d.path])

test_base.main(globals(), __name__ == "__main__")
