"""Tests for attrs library in attr_overlay.py."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class TestAttrib(test_base.BaseTest):
  """Tests for attr.ib."""

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s
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
        def __init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_interpreter_class(self):
    ty = self.Infer("""
      import attr
      class A: pass
      @attr.s
      class Foo:
        x = attr.ib(type=A)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      class A: ...
      @attr.s
      class Foo:
        x: A
        __attrs_attrs__: tuple[attr.Attribute[A], ...]
        def __init__(self, x: A) -> None: ...
    """)

  def test_typing(self):
    ty = self.Infer("""
      from typing import List
      import attr
      @attr.s
      class Foo:
        x = attr.ib(type=List[int])
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import List
      @attr.s
      class Foo:
        x: List[int]
        __attrs_attrs__: tuple[attr.Attribute[List[int]], ...]
        def __init__(self, x: List[int]) -> None: ...
    """)

  def test_union_types(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo:
        x = attr.ib(type=Union[str, int])
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: Union[str, int]
        __attrs_attrs__: tuple[attr.Attribute[Union[str, int]], ...]
        def __init__(self, x: Union[str, int]) -> None: ...
    """)

  def test_comment_annotations(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo:
        x = attr.ib() # type: Union[str, int]
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: Union[str, int]
        y: str
        __attrs_attrs__: tuple[attr.Attribute[Union[str, int]], ...]
        def __init__(self, x: Union[str, int], y: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib() # type: 'Foo'
        y = attr.ib() # type: str
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

  def test_late_annotation_in_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(type='Foo')
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      @attr.s
      class Foo:
        x: Foo
        __attrs_attrs__: tuple[attr.Attribute[Foo], ...]
        def __init__(self, x: Foo) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib() # type: int
        y = attr.ib(type=str)
        z = 1 # class var, should not be in __init__
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
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
        x = attr.ib(type=str) # type: int
        y = attr.ib(type=str, default="")  # type: int
      Foo(x="")  # should not report an error
    """)

  def test_bad_type(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(type=10)  # invalid-annotation
    """)

  def test_name_mangling(self):
    # NOTE: Python itself mangles names starting with two underscores.
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        _x = attr.ib(type=int)
        __y = attr.ib(type=int)
        ___z = attr.ib(type=int)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      @attr.s
      class Foo:
        _x: int
        _Foo__y: int
        _Foo___z: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int, Foo__y: int, Foo___z: int) -> None: ...
    """)

  def test_defaults(self):
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=42)
        y = attr.ib(type=int, default=6)
        z = attr.ib(type=str, default=28)  # annotation-type-mismatch[e]
        a = attr.ib(type=str, default=None)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: int
        y: int
        z: str
        a: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, x: int = ..., y: int = ..., z: str = ...,
                     a: str = ...) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for z"})

  def test_defaults_with_typecomment(self):
    # Typecomments should override the type of default
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=42) # type: int
        y = attr.ib(default=42) # type: str  # annotation-type-mismatch[e]
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

  def test_factory_class(self):
    ty = self.Infer("""
      import attr
      class CustomClass:
        pass
      @attr.s
      class Foo:
        x = attr.ib(factory=list)
        y = attr.ib(factory=CustomClass)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      class CustomClass: ...
      @attr.s
      class Foo:
        x: list
        y: CustomClass
        __attrs_attrs__: tuple[attr.Attribute[Union[list, CustomClass]], ...]
        def __init__(self, x: list = ..., y: CustomClass = ...) -> None: ...
    """)

  def test_factory_function(self):
    ty = self.Infer("""
      import attr
      class CustomClass:
        pass
      def unannotated_func():
        return CustomClass()
      @attr.s
      class Foo:
        x = attr.ib(factory=locals)
        y = attr.ib(factory=unannotated_func)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any, Dict, Union
      class CustomClass: ...
      def unannotated_func() -> CustomClass: ...
      @attr.s
      class Foo:
        x: Dict[str, Any]
        y: Any  # b/64832148: the return type isn't inferred early enough
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, x: Dict[str, object] = ..., y = ...) -> None: ...
    """)

  def test_verbose_factory(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=attr.Factory(list))
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: list
        __attrs_attrs__: tuple[attr.Attribute[list], ...]
        def __init__(self, x: list = ...) -> None: ...
    """)

  def test_bad_factory(self):
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=attr.Factory(42))  # wrong-arg-types[e1]
        y = attr.ib(factory=42)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Callable.*int",
                                     "e2": r"Callable.*int"})

  def test_default_factory_clash(self):
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=None, factory=list)  # duplicate-keyword-argument[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"default"})

  def test_takes_self(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=attr.Factory(len, takes_self=True))
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      @attr.s
      class Foo:
        x: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, x: int = ...) -> None: ...
    """)

  def test_default_none(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=None)
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo:
        x: Any
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, x: Any = ...) -> None: ...
    """)

  def test_annotation_type(self):
    ty = self.Infer("""
      from typing import List
      import attr
      @attr.s
      class Foo:
        x = attr.ib(type=List)
      x = Foo([]).x
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      @attr.s
      class Foo:
        x: list
        __attrs_attrs__: tuple[attr.Attribute[list], ...]
        def __init__(self, x: list) -> None: ...
      x: list
    """)

  def test_instantiation(self):
    self.Check("""
      import attr
      class A:
        def __init__(self):
          self.w = None
      @attr.s
      class Foo:
        x = attr.ib(type=A)
        y = attr.ib()  # type: A
        z = attr.ib(factory=A)
      foo = Foo(A(), A())
      foo.x.w
      foo.y.w
      foo.z.w
    """)

  def test_init(self):
    self.Check("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(init=False, default='')  # type: str
        y = attr.ib()  # type: int
      foo = Foo(42)
      foo.x
      foo.y
    """)

  def test_init_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(init=False, default='')  # type: str
        y = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class Foo:
        x: str
        y: int
        __attrs_attrs__: tuple[attr.Attribute[Union[str, int]], ...]
        def __init__(self, y: int) -> None: ...
    """)

  def test_init_bad_constant(self):
    err = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(init=0)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(err, {"e": r"bool.*int"})

  def test_init_bad_kwarg(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(init=__random__)  # type: str  # not-supported-yet
    """)

  def test_class(self):
    self.assertNoCrash(self.Check, """
      import attr
      class X(attr.make_class('X', {'y': attr.ib(default=None)})):
        pass
    """)

  def test_base_class_attrs(self):
    self.Check("""
      import attr
      @attr.s
      class A:
        a = attr.ib()  # type: int
      @attr.s
      class B:
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        c = attr.ib()  # type: int
      x = C(10, 'foo', 42)
      x.a
      x.b
      x.c
    """)

  def test_base_class_attrs_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class A:
        a = attr.ib()  # type: int
      @attr.s
      class B:
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class A:
        a: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, a: int) -> None: ...
      @attr.s
      class B:
        b: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, b: str) -> None: ...
      @attr.s
      class C(A, B):
        c: int
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, a: int, b: str, c: int) -> None: ...
    """)

  def test_base_class_attrs_override_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class A:
        a = attr.ib()  # type: int
      @attr.s
      class B:
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        a = attr.ib()  # type: str
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class A:
        a: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, a: int) -> None: ...
      @attr.s
      class B:
        b: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, b: str) -> None: ...
      @attr.s
      class C(A, B):
        a: str
        c: int
        __attrs_attrs__: tuple[attr.Attribute[Union[str, int]], ...]
        def __init__(self, b: str, a: str, c: int) -> None: ...
    """)

  def test_base_class_attrs_init(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class A:
        a = attr.ib(init=False)  # type: int
      @attr.s
      class B:
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Union
      @attr.s
      class A:
        a: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self) -> None: ...
      @attr.s
      class B:
        b: str
        __attrs_attrs__: tuple[attr.Attribute[str], ...]
        def __init__(self, b: str) -> None: ...
      @attr.s
      class C(A, B):
        c: int
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, b: str, c: int) -> None: ...
    """)

  def test_base_class_attrs_abstract_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(__any_object__):
        a = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo(Any):
        a: int
        __attrs_attrs__: tuple[attr.Attribute[int], ...]
        def __init__(self, a: int) -> None: ...
    """)

  def test_method_decorators(self):
    # Test for:
    # - validator decorator does not throw an error
    # - default decorator sets type if it isn't set
    # - default decorator does not override type
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo:
        a = attr.ib()
        b = attr.ib()
        c = attr.ib(type=str)  # annotation-type-mismatch[e]
        @a.validator
        def validate(self, attribute, value):
          pass
        @a.default
        def default_a(self):
          # type: (...) -> int
          return 10
        @b.default
        def default_b(self):
          return 10
        @c.default
        def default_c(self):
          # type: (...) -> int
          return 10
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any, Union
      @attr.s
      class Foo:
        a: int
        b: int
        c: str
        __attrs_attrs__: tuple[attr.Attribute[Union[int, str]], ...]
        def __init__(self, a: int = ..., b: int = ..., c: str = ...) -> None: ...
        def default_a(self) -> int: ...
        def default_b(self) -> int: ...
        def default_c(self) -> int: ...
        def validate(self, attribute, value) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for c"})

  def test_default_decorator_using_self(self):
    # default_b refers to self.a; the method itself will be annotated with the
    # correct type, but since this happens after the attribute defaults have
    # been processed, b will have an inferred default types of `Any` rather than
    # `int`.
    #
    # default_c refers to self.b, which has been inferred as `Any`, so default_c
    # gets a type of `-> Any`, but since the type annotation for c is more
    # specific it overrides that.
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        a = attr.ib(default=42)
        b = attr.ib()
        c = attr.ib(type=str)
        @b.default
        def default_b(self):
          return self.a
        @c.default
        def default_c(self):
          return self.b
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any
      @attr.s
      class Foo:
        a: int
        b: Any
        c: str
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, a: int = ..., b = ..., c: str = ...) -> None: ...
        def default_b(self) -> int: ...
        def default_c(self) -> Any: ...
    """)

  def test_repeated_default(self):
    # Regression test for a bug where `params` and `calls` shared an underlying
    # list object, so modifying one affected the type of the other.
    self.Check("""
      import attr

      class Call:
        pass

      @attr.s
      class Function:
        params = attr.ib(factory=list)
        calls = attr.ib(factory=list)

      class FunctionMap:

        def __init__(self, index):
          self.fmap = {"": Function()}

        def print_params(self):
          for param in self.fmap[""].params:
            print(param.name)

        def add_call(self, call):
          self.fmap[""].calls.append(Call())
    """)

  def test_empty_factory(self):
    ty = self.Infer("""
      import attr
      FACTORIES = []
      @attr.s
      class Foo:
        x = attr.ib(factory=FACTORIES[0])
      Foo(x=0)  # should not be an error
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      from typing import Any, List
      FACTORIES: List[nothing]
      @attr.s
      class Foo:
        x: Any
        __attrs_attrs__: tuple[attr.Attribute, ...]
        def __init__(self, x = ...) -> None: ...
    """)

  def test_empty_tuple_default(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=())
    """)
    self.assertTypesMatchPytd(ty, """
      import attr
      @attr.s
      class Foo:
        x: tuple
        __attrs_attrs__: tuple[attr.Attribute[tuple], ...]
        def __init__(self, x: tuple = ...) -> None: ...
    """)

  def test_long_alias(self):
    # Tests an [annotation-type-mismatch] bug that appears when the
    # "serious-business alias" for attr.ib is used.
    self.Check("""
      import attr
      @attr.s
      class Foo:
        x= attr.attrib(default=0)  # type: int
    """)

  def test_typevar_in_type_arg(self):
    self.Check("""
      import attr
      from typing import Callable, TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo:
        f = attr.ib(type=Callable[[T], T])
      assert_type(Foo(__any_object__).f(0), int)
    """)

  def test_bad_typevar_in_type_arg(self):
    self.CheckWithErrors("""
      import attr
      from typing import TypeVar
      T = TypeVar('T')
      @attr.s
      class Foo:
        x = attr.ib(type=T)  # invalid-annotation
    """)

  def test_bad_constructor(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=10, init=0)  # wrong-arg-types
      a = Foo().x
      assert_type(a, int)
    """)

  def test_bad_factory_constructor(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(default=10)
        y = attr.ib(factory=10, type=int)  # wrong-arg-types
    """)

  def test_multiple_bad_constructor_args(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(init=0, validator=10, type=int)  # wrong-arg-types  # wrong-arg-types
      a = Foo(10).x
      assert_type(a, int)
    """)

  def test_extra_constructor_args(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(bar=10, type=int)  # wrong-keyword-args
      a = Foo(10).x
      assert_type(a, int)
    """)

  @test_base.skip("b/203591182")
  def test_duplicate_constructor_args(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo:
        x = attr.ib(10, default='a')  # duplicate-keyword-argument
      a = Foo().x
      assert_type(a, int)
    """)


class TestAttrs(test_base.BaseTest):
  """Tests for attr.s."""

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s()
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
        def __init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_no_init(self):
    ty = self.Infer("""
      import attr
      @attr.s(init=False)
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
        def __attrs_init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_init_bad_constant(self):
    err = self.CheckWithErrors("""
      import attr
      @attr.s(init=0)  # wrong-arg-types[e]
      class Foo:
        pass
    """)
    self.assertErrorRegexes(err, {"e": r"bool.*int"})

  def test_bad_kwarg(self):
    self.CheckWithErrors("""
      import attr
      @attr.s(init=__random__)  # not-supported-yet
      class Foo:
        pass
    """)

  def test_depth(self):
    self.Check("""
      import attr
      def f():
        @attr.s
        class Foo:
          pass
    """, maximum_depth=1)

  def test_signature(self):
    self.Check("""
      import attr
      @attr.s()
      class A:
        id = attr.ib(
            default='', converter=str,
            on_setattr=attr.setters.convert)
    """)


class TestInheritedAttrib(test_base.BaseTest):
  """Tests for attrs in a different module."""

  def test_attrib_wrapper(self):
    foo_ty = self.Infer("""
      import attr
      def attrib_wrapper(*args, **kwargs):
        return attr.ib(*args, **kwargs)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import attr
        import foo
        @attr.s()
        class Foo:
          x: int = foo.attrib_wrapper()
          y = foo.attrib_wrapper(type=int)
        a = Foo(10, 10)
        b = Foo(10, '10')  # The wrapper returns attr.ib(Any) so y.type is lost
        c = Foo(10, 20, 30)  # wrong-arg-count
        d = Foo('10', 20)  # wrong-arg-types
      """, pythonpath=[d.path])

  def test_attrib_wrapper_kwargs(self):
    foo_ty = self.Infer("""
      import attr
      def kw_attrib(typ):
        return attr.ib(typ, kw_only=True)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import attr
        import foo
        @attr.s()
        class Foo:
          x = foo.kw_attrib(int)
        a = Foo(10)  # missing-parameter
        b = Foo(x=10)
      """, pythonpath=[d.path])

  def test_wrapper_setting_type(self):
    foo_ty = self.Infer("""
      import attr
      def int_attrib():
        return attr.ib(type=int)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import attr
        import foo
        @attr.s()
        class Foo(object):  # invalid-annotation
          x: int = foo.int_attrib()
      """, pythonpath=[d.path])

  def test_wrapper_setting_default(self):
    foo_ty = self.Infer("""
      import attr
      def default_attrib(typ):
        return attr.ib(type=typ, default=None)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.Check("""
        import attr
        import foo
        @attr.s()
        class Foo:
          y = attr.ib(default = 10)
          x = foo.default_attrib(int)
        a = Foo()
      """, pythonpath=[d.path])

  def test_override_protected_member(self):
    foo_ty = self.Infer("""
      import attr
      @attr.s
      class A:
        _x = attr.ib(type=str)
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      self.CheckWithErrors("""
        import attr
        import foo
        @attr.s()
        class B(foo.A):
          _x = attr.ib(init=False, default='')
          y = attr.ib(type=int)
        a = foo.A('10')
        b = foo.A(x='10')
        c = B(10)
        d = B(y=10)
        e = B('10', 10)  # wrong-arg-count
      """, pythonpath=[d.path])


if __name__ == "__main__":
  test_base.main()
