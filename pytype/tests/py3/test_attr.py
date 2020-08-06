# Lint as: python3
"""Tests for attrs library in attr_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


class TestAttrib(test_base.TargetPython3BasicTest):
  """Tests for attr.ib."""

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

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

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

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
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):  # invalid-annotation
        x : int = attr.ib(type=str)
    """)

  def test_defaults_with_annotation(self):
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x: int = attr.ib(default=42)
        y: str = attr.ib(default=42)  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x: int = ..., y: str = ...) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for y"})

  def test_cannot_decorate(self):
    # Tests the attr.s decorator being passed an object it can't process.
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Type
        class Foo: ...
        def decorate(cls: Type[Foo]) -> Type[Foo]: ...
      """)
      ty = self.Infer("""
        import attr
        import foo
        @attr.s
        @foo.decorate
        class Bar(foo.Foo): ...
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      attr: module
      foo: module
      Bar: Type[foo.Foo]
    """)

  def test_conflicting_annotations(self):
    # If an annotation has multiple visible values, they must be the same.
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        if __random__:
          v: int = attr.ib()
        else:
          v: int = attr.ib()
      @attr.s
      class Bar(object):
        if __random__:
          v: int = attr.ib()
        else:
          v: str = attr.ib()  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": "'int or str' for v"})

  def test_kw_only(self):
    ty = self.Infer("""
      import attr
      @attr.s(kw_only=False)
      class Foo(object):
        x = attr.ib(default=42)
        y = attr.ib(type=int, kw_only=True)
        z = attr.ib(type=str, default="hello")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: int
        y: int
        z: str
        def __init__(self, x: int = ..., z: str = ..., *, y: int) -> None: ...
    """)


class TestAttrs(test_base.TargetPython3FeatureTest):
  """Tests for attr.s."""

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

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

  def test_kw_only_with_defaults(self):
    ty = self.Infer("""
      import attr
      @attr.s(kw_only=True)
      class Foo(object):
        x = attr.ib(default=1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: int
        def __init__(self, *, x : int = ...) -> None: ...
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
    self.CheckWithErrors("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):  # invalid-function-definition
        x: int = 10
        y: str
    """)

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

  def test_partial_auto_attribs(self):
    # Tests that we can have multiple attrs classes with different kwargs.
    # If Bar accidentally uses auto_attribs=True, then its __init__ signature
    # will be incorrect, since `baz` won't be recognized as an attr.
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo:
        foo: str
      @attr.s
      class Bar:
        bar: str = attr.ib()
        baz = attr.ib()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo:
        foo: str
        def __init__(self, foo: str) -> None: ...
      class Bar:
        bar: str
        baz: Any
        def __init__(self, bar: str, baz) -> None: ...
    """)

  def test_classvar_auto_attribs(self):
    ty = self.Infer("""
      from typing import ClassVar
      import attr
      @attr.s(auto_attribs=True)
      class Foo(object):
        x: ClassVar[int] = 10
        y: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, y: str = ...) -> None: ...
    """)


test_base.main(globals(), __name__ == "__main__")
