"""Tests for the dataclasses overlay."""

from pytype.tests import test_base


class TestDataclass(test_base.TargetPython3FeatureTest):
  """Tests for @dataclass."""

  def test_basic(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: bool
        y: int
        z: str
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: bool
        y: int
        z: str
        def __init__(self, x: bool, y: int, z: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: 'Foo'
        y: str
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_redefine(self):
    """The first annotation should determine the order."""
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: int
        y: int
        x: str = 'hello'
        y = 10
    """)
    self.assertTypesMatchPytd(ty, """
      dataclasses: module
      class Foo(object):
        y: int
        x: str
        def __init__(self, x: str = ..., y: int = ...) -> None: ...
    """)

  def test_redefine_as_method(self):
    # NOTE: This arguably does the wrong thing, but it is what dataclass
    # actually does. We might want to make it an error.
    ty = self.Infer("""
      import dataclasses
      @dataclasses.dataclass
      class Foo(object):
        x: str = 'hello'
        y: int = 10
        def x(self):
          return 10
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      dataclasses: module
      class Foo(object):
        y: int
        def __init__(self, x: Callable = ..., y: int = ...) -> None: ...
        def x(self) -> int: ...
    """)


test_base.main(globals(), __name__ == "__main__")
