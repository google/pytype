"""Tests for attrs library in attr_overlay.py."""

from pytype.tests import test_base


class TestAttrib(test_base.TargetPython3BasicTest):
  """Tests for attr.ib using type annotations."""

  def test_factory_function(self):
    ty = self.Infer("""
      import attr
      class CustomClass(object):
        pass
      def annotated_func() -> CustomClass:
        return CustomClass()
      @attr.s
      class Foo(object):
        x = attr.ib(factory=annotated_func)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class CustomClass(object): ...
      def annotated_func() -> CustomClass: ...
      class Foo(object):
        x: CustomClass
        def __init__(self, x: CustomClass = ...) -> None: ...
    """)


class TestAttribPy3(test_base.TargetPython3FeatureTest):
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
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x : int = attr.ib(type=str)
    """)
    self.assertErrorLogIs(errors, [(4, "invalid-annotation")])

  def test_defaults_with_annotation(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x: int = attr.ib(default=42)
        y: str = attr.ib(default=42)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x: int = ..., y: str = ...) -> None: ...
    """)


class TestAttrs(test_base.TargetPython3FeatureTest):
  """Tests for attr.s."""

  def test_kw_only(self):
    ty = self.Infer("""
      import attr
      @attr.s(kw_only=True)
      class Foo(object):
        x = attr.ib()
        y = attr.ib(type=int)
        z = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: Any
        y: int
        z: str
        def __init__(self, *, x, y: int, z: str) -> None: ...
    """)

  def test_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        x: int
        y: 'Foo'
        z = 10
        a: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: Foo
        z: int
        a: str
        def __init__(self, x: int, y: Foo, a: str = ...) -> None: ...
    """)

  def test_redefined_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        x = 10
        y: int
        x: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        y: int
        x: str
        def __init__(self, y: int, x: str = ...) -> None: ...
    """)

  def test_non_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        @classmethod
        def foo(cls):
          pass
        @staticmethod
        def bar(x):
          pass
        _x = 10
        y: str = 'hello'
        @property
        def x(self):
          return self._x
        @x.setter
        def x(self, x):
          self._x = x
        def f(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        _x: int
        x: Any
        y: str
        def __init__(self, y: str = ...) -> None: ...
        def f(self) -> None: ...
        @staticmethod
        def bar(x) -> None: ...
        @classmethod
        def foo(cls) -> None: ...
    """)

  def test_bad_default_param_order(self):
    err = self.CheckWithErrors("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        x: int = 10
        y: str
    """)
    self.assertErrorLogIs(err, [(4, "invalid-function-definition")])

  def test_subclass_auto_attribs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        x: bool
        y: int = 42
      class Bar(Foo):
        def get_x(self):
          return self.x
        def get_y(self):
          return self.y
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: bool
        y: int
        def __init__(self, x: bool, y: int = ...) -> None: ...
      class Bar(Foo):
        def get_x(self) -> bool : ...
        def get_y(self) -> int: ...
    """)


test_base.main(globals(), __name__ == "__main__")
