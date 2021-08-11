"""Tests for attrs library in attr_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


class TestAttrib(test_base.TargetPython3BasicTest):
  """Tests for attr.ib."""

  def test_factory_function(self):
    ty = self.Infer("""
      import attr
      class CustomClass:
        pass
      def annotated_func() -> CustomClass:
        return CustomClass()
      @attr.s
      class Foo:
        x = attr.ib(factory=annotated_func)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class CustomClass: ...
      def annotated_func() -> CustomClass: ...
      @attr.s
      class Foo:
        x: CustomClass
        def __init__(self, x: CustomClass = ...) -> None: ...
    """)

  def test_attr_default_dict(self):
    self.Check("""
      import attr
      @attr.s
      class Dog2():
        dog_attr = attr.ib(default='woofing', **dict())

        def make_puppy(self) -> 'Dog2':
          return Dog2()
    """)


class TestAttribConverters(test_base.TargetPython3BasicTest):
  """Tests for attr.ib with converters."""

  def test_annotated_converter(self):
    self.Check("""
      import attr
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(converter=convert)
      Foo(x='123')
    """)

  def test_type_and_converter(self):
    self.Check("""
      import attr
      def convert(input: str):
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=int, converter=convert)
      Foo(x='123')
    """)

  def test_unannotated_converter_with_type(self):
    # TODO(b/135553563): This test should fail once we get better type checking
    # of converter functions.
    self.Check("""
      import attr
      def convert(input):
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=int, converter=convert)
      Foo(x='123')
      Foo(x=[1,2,3])  # does not complain, input is treated as Any
    """)

  def test_annotated_converter_with_mismatched_type(self):
    # TODO(b/135553563): This test should fail once we start checking the
    # consistency of the converter and the explicit type.
    self.Check("""
      import attr
      def convert(input) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=str, converter=convert)
      foo = Foo(x=123)
      assert_type(foo.x, str)  # the explicit type overrides the converter
    """)

  def test_wrong_converter_arity(self):
    # TODO(b/135553563): Add a custom error message
    self.CheckWithErrors("""
      import attr
      def convert(x, y) -> int:
        return 42
      @attr.s
      class Foo:
        x = attr.ib(type=str, converter=convert)  # wrong-arg-types
    """)

  def test_converter_with_default_args(self):
    self.Check("""
      import attr
      def convert(x, y=10) -> int:
        return 42
      @attr.s
      class Foo:
        x = attr.ib(type=str, converter=convert)
    """)

  def test_converter_with_varargs(self):
    self.Check("""
      import attr
      def convert(*args, **kwargs) -> int:
        return 42
      @attr.s
      class Foo:
        x = attr.ib(type=str, converter=convert)
    """)


class TestAttribPy3(test_base.TargetPython3FeatureTest):
  """Tests for attr.ib using PEP526 syntax."""

  def test_variable_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x : int = attr.ib()
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
        x: int
        y: str
        def __init__(self, x: int, y: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x : 'Foo' = attr.ib()
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x : int = attr.ib()
        y = attr.ib(type=str)
        z : int = 1 # class var, should not be in __init__
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
        x: int
        y: str
        z: int
        def __init__(self, x: int, y: str) -> None: ...
    """)

  def test_type_clash(self):
    # Note: explicitly inheriting from object keeps the line number of the error
    # stable between Python versions.
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
      class Foo:
        x: int = attr.ib(default=42)
        y: str = attr.ib(default=42)  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
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
      class Foo:
        if __random__:
          v: int = attr.ib()
        else:
          v: int = attr.ib()
      @attr.s
      class Bar:
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
      class Foo:
        x = attr.ib(default=42)
        y = attr.ib(type=int, kw_only=True)
        z = attr.ib(type=str, default="hello")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      @attr.s
      class Foo:
        x: int
        y: int
        z: str
        def __init__(self, x: int = ..., z: str = ..., *, y: int) -> None: ...
    """)

  def test_generic(self):
    ty = self.Infer("""
      import attr
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x: T = attr.ib()
        y = attr.ib()  # type: T
      foo1 = Foo[int](x=__any_object__, y=__any_object__)
      x1, y1 = foo1.x, foo1.y
      foo2 = Foo(x='', y='')
      x2, y2 = foo2.x, foo2.y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      attr: module
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x: T
        y: T
        def __init__(self, x: T, y: T) -> None:
          self = Foo[T]
      foo1: Foo[int]
      x1: int
      y1: int
      foo2: Foo[str]
      x2: str
      y2: str
    """)

  def test_generic_auto_attribs(self):
    ty = self.Infer("""
      import attr
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @attr.s(auto_attribs=True)
      class Foo(Generic[T]):
        x: T
      foo1 = Foo[int](x=__any_object__)
      x1 = foo1.x
      foo2 = Foo(x='')
      x2 = foo2.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, TypeVar
      attr: module
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x: T
        def __init__(self, x: T) -> None:
          self = Foo[T]
      foo1: Foo[int]
      x1: int
      foo2: Foo[str]
      x2: str
    """)

  def test_typevar_in_type_arg_generic(self):
    self.Check("""
      import attr
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x = attr.ib(type=T)
      assert_type(Foo[int](__any_object__).x, int)
    """)


class TestAttrs(test_base.TargetPython3FeatureTest):
  """Tests for attr.s."""

  def test_kw_only(self):
    ty = self.Infer("""
      import attr
      @attr.s(kw_only=True)
      class Foo:
        x = attr.ib()
        y = attr.ib(type=int)
        z = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      @attr.s
      class Foo:
        x: Any
        y: int
        z: str
        def __init__(self, *, x, y: int, z: str) -> None: ...
    """)

  def test_kw_only_with_defaults(self):
    ty = self.Infer("""
      import attr
      @attr.s(kw_only=True)
      class Foo:
        x = attr.ib(default=1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      @attr.s
      class Foo:
        x: int
        def __init__(self, *, x : int = ...) -> None: ...
    """)

  def test_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo:
        x: int
        y: 'Foo'
        z = 10
        a: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
        x: int
        y: Foo
        a: str
        z: int
        def __init__(self, x: int, y: Foo, a: str = ...) -> None: ...
    """)

  def test_redefined_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo:
        x = 10
        y: int
        x: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      @attr.s
      class Foo:
        y: int
        x: str
        def __init__(self, y: int, x: str = ...) -> None: ...
    """)

  def test_non_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.s(auto_attribs=True)
      class Foo:
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
        def x(self, x: int):
          self._x = x
        def f(self):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Annotated
      attr: module
      @attr.s
      class Foo:
        y: str
        _x: int
        x: Annotated[int, 'property']
        def __init__(self, y: str = ...) -> None: ...
        def f(self) -> None: ...
        @staticmethod
        def bar(x) -> None: ...
        @classmethod
        def foo(cls) -> None: ...
    """)

  def test_bad_default_param_order(self):
    # Note: explicitly inheriting from object keeps the line number of the error
    # stable between Python versions.
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
      class Foo:
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
      @attr.s
      class Foo:
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
      @attr.s
      class Foo:
        foo: str
        def __init__(self, foo: str) -> None: ...
      @attr.s
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
      class Foo:
        x: ClassVar[int] = 10
        y: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import ClassVar
      attr: module
      @attr.s
      class Foo:
        y: str
        x: ClassVar[int]
        def __init__(self, y: str = ...) -> None: ...
    """)

  def test_wrapper(self):
    ty = self.Infer("""
      import attr
      def s(*args, **kwargs):
        return attr.s(*args, auto_attribs=True, **kwargs)
      @s
      class Foo:
        x: int
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      attr: module
      def s(*args, **kwargs) -> Callable: ...
      @attr.s
      class Foo:
        x: int
        def __init__(self, x: int) -> None: ...
    """)


class TestPyiAttrs(test_base.TargetPython3FeatureTest):
  """Tests for @attr.s in pyi files."""

  def test_basic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          x: int
          y: str
      """)
      self.Check("""
        import foo
        x = foo.A(10, 'hello')
      """, pythonpath=[d.path])

  def test_docstring(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          __doc__: str  # should be filtered out
          x: int
          y: str
      """)
      self.Check("""
        import foo
        x = foo.A(10, 'hello')
      """, pythonpath=[d.path])

  def test_type_mismatch(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          x: int
          y: str
      """)
      self.CheckWithErrors("""
        import foo
        x = foo.A(10, 20)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_subclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          x: bool
          y: int
      """)
      ty = self.Infer("""
        import attr
        import foo
        @attr.s(auto_attribs=True)
        class Foo(foo.A):
          z: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        attr: module
        foo: module
        @attr.s
        class Foo(foo.A):
          z: str
          def __init__(self, x: bool, y: int, z: str = ...) -> None: ...
      """)

  def test_subclass_from_same_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          x: bool
          y: int

        @attr.s
        class B(A):
          z: str
      """)
      ty = self.Infer("""
        import attr
        import foo
        @attr.s(auto_attribs=True)
        class Foo(foo.B):
          a: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        attr: module
        foo: module
        @attr.s
        class Foo(foo.B):
          a: str
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_from_different_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("bar.pyi", """
        import attr
        @attr.s
        class A:
          x: bool
          y: int
      """)
      d.create_file("foo.pyi", """
        import attr
        import bar
        @attr.s
        class B(bar.A):
          z: str
      """)
      ty = self.Infer("""
        import attr
        import foo
        @attr.attrs(auto_attribs=True)
        class Foo(foo.B):
          a: str = "hello"
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        attr: module
        foo: module
        @attr.s
        class Foo(foo.B):
          a: str
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_with_kwonly(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        @attr.s
        class A:
          x: bool
          y: int
          def __init__(self, x: bool, *, y: int = ...): ...
      """)
      ty = self.Infer("""
        import attr
        import foo
        @attr.s(auto_attribs=True)
        class Foo(foo.A):
          z: str
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        attr: module
        foo: module
        @attr.s
        class Foo(foo.A):
          z: str
          def __init__(self, x: bool, z: str, *, y: int = ...) -> None: ...
      """)


test_base.main(globals(), __name__ == "__main__")
