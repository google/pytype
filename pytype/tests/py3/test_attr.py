"""Tests for attrs library in attr_overlay.py."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestAttrib(test_utils.TestAttrMixin,
                 test_base.TargetPython3FeatureTest):
  """Tests for attr.ib using PEP526 syntax."""

  def test_variable_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x : int = attr.ib()
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x: int, y: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x : 'Foo' = attr.ib()
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x : int = attr.ib()
        y = attr.ib(type=str)
        z : int = 1 # class var, should not be in __init__
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        z: int
        def __init__(self, x: int, y: str) -> None: ...
    """)

  def test_type_clash(self):
    _, errors = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x : int = attr.ib(type=str)
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation")])


test_base.main(globals(), __name__ == "__main__")
