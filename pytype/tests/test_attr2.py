"""Tests for attrs library in attr_overlay.py."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class TestAttrib(test_base.BaseTest):
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
      import attr
      class CustomClass: ...
      def annotated_func() -> CustomClass: ...
      @attr.s
      class Foo:
        x: CustomClass
        __attrs_attrs__: tuple[attr.Attribute[CustomClass], ...]
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


class TestAttribConverters(test_base.BaseTest):
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
    # of converter functions. This would need us to run the converter every time
    # we construct a new instance of Foo.
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
    self.CheckWithErrors("""
      import attr
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=str, converter=convert)  # annotation-type-mismatch
      foo = Foo(x=123)  # wrong-arg-types
      assert_type(foo.x, str)
    """)

  def test_converter_without_return_annotation(self):
    self.CheckWithErrors("""
      import attr
      def convert(input: str):
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(converter=convert)
      foo = Foo(x=123) # wrong-arg-types
      assert_type(foo.x, int)
    """)

  def test_converter_with_union_type(self):
    self.Check("""
      import attr
      from typing import Union
      def convert(input: str):
        if __random__:
          return input
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(converter=convert)
      foo = Foo(x='123')
      assert_type(foo.x, Union[int, str])
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
        x = attr.ib(converter=convert)
    """)

  def test_converter_with_varargs(self):
    self.CheckWithErrors("""
      import attr
      def convert(*args, **kwargs) -> int:
        return 42
      @attr.s
      class Foo:
        x = attr.ib(converter=convert)
    """)

  def test_converter_conflicts_with_type(self):
    self.CheckWithErrors("""
      import attr
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=list, converter=convert)  # annotation-type-mismatch
      foo = Foo(x='123')
      assert_type(foo.x, list)
    """)

  def test_converter_conflicts_with_annotation(self):
    self.CheckWithErrors("""
      import attr
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x: list = attr.ib(converter=convert)  # annotation-type-mismatch
      foo = Foo(x='123')
      assert_type(foo.x, list)
    """)

  def test_converter_conflicts_with_default(self):
    self.CheckWithErrors("""
      import attr
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(converter=convert, default='a')  # annotation-type-mismatch
      foo = Foo(x='123')
      assert_type(foo.x, int)
    """)

  def test_type_compatible_with_converter(self):
    # type is not identical to converter type but includes it.
    self.Check("""
      import attr
      from typing import Optional
      def convert(input: str) -> int:
        return int(input)
      @attr.s
      class Foo:
        x = attr.ib(type=Optional[int], converter=convert)
      foo = Foo(x='123')
      assert_type(foo.x, Optional[int])
    """)

  def test_callable_as_converter(self):
    self.Check("""
      import attr
      from typing import Callable
      def f() -> Callable[[int], str]:
        return __any_object__
      @attr.s
      class Foo:
        x = attr.ib(converter=f())
      foo = Foo(x=0)
      assert_type(foo.x, str)
    """)

  def test_partial_as_converter(self):
    self.Check("""
      import attr
      import functools
      def f(x: int) -> str:
        return ''
      @attr.s
      class Foo:
        x = attr.ib(converter=functools.partial(f))
      # We don't yet infer the right type for Foo.x in this case, but we at
      # least want to check that constructing a Foo doesn't generate errors.
      Foo(x=0)
    """)


class TestAttribPy3(test_base.BaseTest):
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: Foo
        y: str
        __attrs_attrs__: tuple[attr.Attribute[Union[Foo, str]], ...]
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: str
        z: int
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, x: int = ..., y: str = ...) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for y"})

  def test_cannot_decorate(self):
    # Tests the attr.s decorator being passed an object it can't process.
    with test_utils.Tempdir() as d:
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
      import attr
      import foo
      from typing import Type
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
      import attr
      from typing import Any, Union
      @attr.s
      class Foo:
        x: int
        y: int
        z: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
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
      import attr
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x: T
        y: T
        __attrs_attrs__: tuple[attr.Attribute[T], ...]
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
      import attr
      from typing import Generic, TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo(Generic[T]):
        x: T
        __attrs_attrs__: tuple[attr.Attribute[T], ...]
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


class TestAttrs(test_base.BaseTest):
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
      import attr
      from typing import Any
      @attr.s
      class Foo:
        x: Any
        y: int
        z: str
        __attrs_attrs__: tuple[attr.Attribute, ...]
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
      import attr
      from typing import Any
      @attr.s
      class Foo:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, *, x : int = ...) -> None: ...
    """)

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: Foo
        a: str
        __attrs_attrs__: tuple[attr.Attribute[Union[Foo, int, str]], ...]
        z: int
        def __init__(self, x: int, y: Foo, a: str = ...) -> None: ...
    """)

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      from typing import Union
      @attr.s
      class Foo:
        y: int
        x: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, y: int, x: str = ...) -> None: ...
    """)

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      from typing import Any, Annotated
      @attr.s
      class Foo:
        y: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        _x: int
        x: Annotated[int, 'property']
        def __init__(self, y: str = ...) -> None: ...
        def f(self) -> None: ...
        @staticmethod
        def bar(x) -> None: ...
        @classmethod
        def foo(cls) -> None: ...
    """)

  def test_callable_attrib(self):
    ty = self.Infer("""
      import attr
      from typing import Callable
      @attr.s(auto_attribs=True)
      class Foo:
        x: Callable = lambda x: x
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Callable, Union
      @attr.s
      class Foo:
        x: Callable
        __attrs_attrs__: tuple[attr.Attribute[Callable], ...]
        def __init__(self, x: Callable = ...) -> None: ...
    """)

  def test_auto_attrs_with_dataclass_constructor(self):
    ty = self.Infer("""
      import attr
      @attr.dataclass
      class Foo:
        x: int
        y: 'Foo'
        z = 10
        a: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: Foo
        a: str
        __attrs_attrs__: tuple[attr.Attribute[Union[Foo, int, str]], ...]
        z: int
        def __init__(self, x: int, y: Foo, a: str = ...) -> None: ...
    """)

  def test_init_false_generates_attrs_init(self):
    ty = self.Infer("""
      import attr
      @attr.s(init=False)
      class Foo:
        x = attr.ib()
        y: int = attr.ib()
        z = attr.ib(type=str, default="bar")
        t = attr.ib(init=False, default=5)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo:
        x: Any
        y: int
        z: str
        t: int
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __attrs_init__(self, x, y: int, z: str = "bar") -> None: ...
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

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      @attr.s
      class Foo:
        x: bool
        y: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: bool, y: int = ...) -> None: ...
      class Bar(Foo):
        def get_x(self) -> bool : ...
        def get_y(self) -> int: ...
    """)

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      from typing import Any
      @attr.s
      class Foo:
        foo: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, foo: str) -> None: ...
      @attr.s
      class Bar:
        bar: str
        baz: Any
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, bar: str, baz) -> None: ...
    """)

  # Mirrored in TestAttrsNextGenApi, except with @attr.define
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
      import attr
      from typing import ClassVar
      @attr.s
      class Foo:
        y: str
        x: ClassVar[int]
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
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
      import attr
      from typing import Callable
      def s(*args, **kwargs) -> Callable: ...
      @attr.s
      class Foo:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int) -> None: ...
    """)


class TestAttrsNextGenApi(test_base.BaseTest):
  """Tests for attrs next generation API, added in attrs version 21.1.0.

  See: https://www.attrs.org/en/stable/api.html#next-gen
  """

  def test_define_auto_detects_auto_attrs_true(self):
    """Test whether @attr.define can detect auto_attrs will default to True.

    This is determined by all variable declarations having a type annotation.
    """
    ty = self.Infer("""
      from typing import Any
      import attr
      @attr.define
      class Foo:
        x: Any
        y: int = attr.field()
        z: str = attr.field(default="bar")
        r: int = 43
        t: int = attr.field(default=5, init=False)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any, Union
      @attr.s(auto_attribs=True)
      class Foo:
        x: Any
        y: int
        z: str
        r: int
        t: int
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, x, y: int, z: str = "bar", r: int = 43) -> None: ...
    """)

  def test_define_auto_detects_auto_attrs_false(self):
    """Test whether @attr.define can detect auto_attrs should default to False.

    This is determined by at least one variable declaration not having a type
    annotation.
    """
    ty = self.Infer("""
      from typing import Any
      import attr
      @attr.define
      class Foo:
        x = None
        y = attr.field(type=int)
        z = attr.field()
        r = attr.field(default="bar")
        t: int = attr.field(default=5, init=False)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo:
        y: int
        z: Any
        r: str
        t: int
        __attrs_attrs__: tuple[attr.Attribute, ...]
        x: None
        def __init__(self, y: int, z, r: str = "bar") -> None: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.define(auto_attribs=True)
      class Foo:
        x: int
        y: 'Foo'
        z = 10
        a: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: Foo
        a: str
        __attrs_attrs__: tuple[attr.Attribute[Union[Foo, int, str]], ...]
        z: int
        def __init__(self, x: int, y: Foo, a: str = ...) -> None: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_redefined_auto_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.define(auto_attribs=True)
      class Foo:
        x = 10
        y: int
        x: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        y: int
        x: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, y: int, x: str = ...) -> None: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_non_attrs(self):
    ty = self.Infer("""
      import attr
      @attr.define(auto_attribs=True)
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
      import attr
      from typing import Any, Annotated
      @attr.s
      class Foo:
        y: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        _x: int
        x: Annotated[int, 'property']
        def __init__(self, y: str = ...) -> None: ...
        def f(self) -> None: ...
        @staticmethod
        def bar(x) -> None: ...
        @classmethod
        def foo(cls) -> None: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_subclass_auto_attribs(self):
    ty = self.Infer("""
      import attr
      @attr.define(auto_attribs=True)
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
      import attr
      @attr.s
      class Foo:
        x: bool
        y: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: bool, y: int = ...) -> None: ...
      class Bar(Foo):
        def get_x(self) -> bool : ...
        def get_y(self) -> int: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_partial_auto_attribs(self):
    # Tests that we can have multiple attrs classes with different kwargs.
    # If Bar accidentally uses auto_attribs=True, then its __init__ signature
    # will be incorrect, since `baz` won't be recognized as an attr.
    ty = self.Infer("""
      import attr
      @attr.define(auto_attribs=True)
      class Foo:
        foo: str
      @attr.s  # Deliberately keeping this one @attr.s, test they work together.
      class Bar:
        bar: str = attr.ib()
        baz = attr.ib()
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo:
        foo: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, foo: str) -> None: ...
      @attr.s
      class Bar:
        bar: str
        baz: Any
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, bar: str, baz) -> None: ...
    """)

  # Mirrored from TestAttrs, except with @attr.define
  def test_classvar_auto_attribs(self):
    ty = self.Infer("""
      from typing import ClassVar
      import attr
      @attr.define(auto_attribs=True)
      class Foo:
        x: ClassVar[int] = 10
        y: str = 'hello'
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import ClassVar
      @attr.s
      class Foo:
        y: str
        x: ClassVar[int]
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, y: str = ...) -> None: ...
    """)

  def test_attrs_namespace(self):
    ty = self.Infer("""
      import attrs
      @attrs.define
      class Foo:
        x: int
      @attrs.mutable
      class Bar:
        x: int
      @attrs.frozen
      class Baz:
        x: int
      @attrs.define
      class Qux:
        x: int = attrs.field(init=False)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      import attrs
      @attr.s
      class Foo:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int) -> None: ...
      @attr.s
      class Bar:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int) -> None: ...
      @attr.s
      class Baz:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int) -> None: ...
      @attr.s
      class Qux:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self) -> None: ...
    """)


class TestPyiAttrs(test_base.BaseTest):
  """Tests for @attr.s in pyi files."""

  def test_basic(self):
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import attr
        from typing import Union
        @attr.s
        class A:
          __doc__: str  # should be filtered out
          x: int
          y: str
          __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
      """)
      self.Check("""
        import foo
        x = foo.A(10, 'hello')
      """, pythonpath=[d.path])

  def test_type_mismatch(self):
    with test_utils.Tempdir() as d:
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
    with test_utils.Tempdir() as d:
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
        import attr
        from typing import Union
        import foo
        @attr.s
        class Foo(foo.A):
          z: str
          __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
          def __init__(self, x: bool, y: int, z: str = ...) -> None: ...
      """)

  def test_subclass_from_same_pyi(self):
    with test_utils.Tempdir() as d:
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
        import attr
        from typing import Union
        import foo
        @attr.s
        class Foo(foo.B):
          a: str
          __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_from_different_pyi(self):
    with test_utils.Tempdir() as d:
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
        import attr
        from typing import Union
        import foo
        @attr.s
        class Foo(foo.B):
          a: str
          __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
          def __init__(self, x: bool, y: int, z: str, a: str = ...) -> None: ...
      """)

  def test_subclass_with_kwonly(self):
    with test_utils.Tempdir() as d:
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
        import attr
        from typing import Union
        import foo
        @attr.s
        class Foo(foo.A):
          z: str
          __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
          def __init__(self, x: bool, z: str, *, y: int = ...) -> None: ...
      """)


class TestPyiAttrsWrapper(test_base.BaseTest):
  """Tests for @attr.s wrappers in pyi files."""

  def test_basic(self):
    foo_ty = self.Infer("""
      import attr
      wrapper = attr.s(kw_only=True, auto_attribs=True)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        @foo.wrapper
        class Foo:
          x: int
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Annotated, Callable

        @attr.s
        class Foo:
          x: int
          __attrs_attrs__: tuple[attr.Attribute[int], ...]
          def __init__(self, *, x: int) -> None: ...
      """)


if __name__ == "__main__":
  test_base.main()
