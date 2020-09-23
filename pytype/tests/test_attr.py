# Lint as: python3
"""Tests for attrs library in attr_overlay.py."""

from pytype.tests import test_base


class TestAttrib(test_base.TargetIndependentTest):
  """Tests for attr.ib."""

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s
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
        def __init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_interpreter_class(self):
    ty = self.Infer("""
      import attr
      class A(object): pass
      @attr.s
      class Foo(object):
        x = attr.ib(type=A)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class A(object): ...
      class Foo(object):
        x: A
        def __init__(self, x: A) -> None: ...
    """)

  def test_typing(self):
    ty = self.Infer("""
      from typing import List
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=List[int])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      attr: module
      class Foo(object):
        x: List[int]
        def __init__(self, x: List[int]) -> None: ...
    """)

  def test_union_types(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=Union[str, int])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      attr: module
      class Foo(object):
        x: Union[str, int]
        def __init__(self, x: Union[str, int]) -> None: ...
    """)

  def test_comment_annotations(self):
    ty = self.Infer("""
      from typing import Union
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: Union[str, int]
        y = attr.ib(type=str)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      attr: module
      class Foo(object):
        x: Union[str, int]
        y: str
        def __init__(self, x: Union[str, int], y: str) -> None: ...
    """)

  def test_late_annotations(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: 'Foo'
        y = attr.ib() # type: str
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: Foo
        y: str
        def __init__(self, x: Foo, y: str) -> None: ...
    """)

  def test_late_annotation_in_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type='Foo')
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: Foo
        def __init__(self, x: Foo) -> None: ...
    """)

  def test_classvar(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib() # type: int
        y = attr.ib(type=str)
        z = 1 # class var, should not be in __init__
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
        x = attr.ib(type=str) # type: int
        y = attr.ib(type=str, default="")  # type: int
      Foo(x="")  # should not report an error
    """)

  def test_bad_type(self):
    self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=10)  # invalid-annotation
    """)

  def test_name_mangling(self):
    # NOTE: Python itself mangles names starting with two underscores.
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        _x = attr.ib(type=int)
        __y = attr.ib(type=int)
        ___z = attr.ib(type=int)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        _x: int
        _Foo__y: int
        _Foo___z: int
        def __init__(self, x: int, Foo__y: int, Foo___z: int) -> None: ...
    """)

  def test_defaults(self):
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=42)
        y = attr.ib(type=int, default=6)
        z = attr.ib(type=str, default=28)  # annotation-type-mismatch[e]
        a = attr.ib(type=str, default=None)
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: int
        z: str
        a: str
        def __init__(self, x: int = ..., y: int = ..., z: str = ...,
                     a: str = ...) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for z"})

  def test_defaults_with_typecomment(self):
    # Typecomments should override the type of default
    ty, err = self.InferWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=42) # type: int
        y = attr.ib(default=42) # type: str  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        y: str
        def __init__(self, x: int = ..., y: str = ...) -> None: ...
    """)
    self.assertErrorRegexes(err, {"e": "annotation for y"})

  def test_factory_class(self):
    ty = self.Infer("""
      import attr
      class CustomClass(object):
        pass
      @attr.s
      class Foo(object):
        x = attr.ib(factory=list)
        y = attr.ib(factory=CustomClass)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      attr: module
      class CustomClass(object): ...
      class Foo(object):
        x: list
        y: CustomClass
        def __init__(self, x: list = ..., y: CustomClass = ...) -> None: ...
    """)

  def test_factory_function(self):
    ty = self.Infer("""
      import attr
      class CustomClass(object):
        pass
      def unannotated_func():
        return CustomClass()
      @attr.s
      class Foo(object):
        x = attr.ib(factory=locals)
        y = attr.ib(factory=unannotated_func)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      attr: module
      class CustomClass(object): ...
      def unannotated_func() -> CustomClass: ...
      class Foo(object):
        x: Dict[str, Any]
        y: Any  # b/64832148: the return type isn't inferred early enough
        def __init__(self, x: Dict[str, object] = ..., y = ...) -> None: ...
    """)

  def test_verbose_factory(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=attr.Factory(list))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      attr: module
      class Foo(object):
        x: list
        def __init__(self, x: list = ...) -> None: ...
    """)

  def test_bad_factory(self):
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=attr.Factory(42))  # wrong-arg-types[e1]
        y = attr.ib(factory=42)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"Callable.*int",
                                     "e2": r"Callable.*int"})

  def test_default_factory_clash(self):
    errors = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=None, factory=list)  # duplicate-keyword-argument[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"default"})

  def test_takes_self(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=attr.Factory(len, takes_self=True))
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: int
        def __init__(self, x: int = ...) -> None: ...
    """)

  def test_default_none(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(default=None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      attr: module
      class Foo(object):
        x: Any
        def __init__(self, x: Any = ...) -> None: ...
    """)

  def test_annotation_type(self):
    ty = self.Infer("""
      from typing import List
      import attr
      @attr.s
      class Foo(object):
        x = attr.ib(type=List)
      x = Foo([]).x
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: list
        def __init__(self, x: list) -> None: ...
      x: list
    """)

  def test_instantiation(self):
    self.Check("""
      import attr
      class A(object):
        def __init__(self):
          self.w = None
      @attr.s
      class Foo(object):
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
      class Foo(object):
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
      class Foo(object):
        x = attr.ib(init=False, default='')  # type: str
        y = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class Foo(object):
        x: str
        y: int
        def __init__(self, y: int) -> None: ...
    """)

  def test_init_bad_constant(self):
    err = self.CheckWithErrors("""
      import attr
      @attr.s
      class Foo(object):
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
      class A(object):
        a = attr.ib()  # type: int
      @attr.s
      class B(object):
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
      class A(object):
        a = attr.ib()  # type: int
      @attr.s
      class B(object):
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class A(object):
        a: int
        def __init__(self, a: int) -> None: ...
      class B(object):
        b: str
        def __init__(self, b: str) -> None: ...
      class C(A, B):
        c: int
        def __init__(self, a: int, b: str, c: int) -> None: ...
    """)

  def test_base_class_attrs_override_type(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class A(object):
        a = attr.ib()  # type: int
      @attr.s
      class B(object):
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        a = attr.ib()  # type: str
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class A(object):
        a: int
        def __init__(self, a: int) -> None: ...
      class B(object):
        b: str
        def __init__(self, b: str) -> None: ...
      class C(A, B):
        a: str
        c: int
        def __init__(self, b: str, a: str, c: int) -> None: ...
    """)

  def test_base_class_attrs_init(self):
    ty = self.Infer("""
      import attr
      @attr.s
      class A(object):
        a = attr.ib(init=False)  # type: int
      @attr.s
      class B(object):
        b = attr.ib()  # type: str
      @attr.s
      class C(A, B):
        c = attr.ib()  # type: int
    """)
    self.assertTypesMatchPytd(ty, """
      attr: module
      class A(object):
        a: int
        def __init__(self) -> None: ...
      class B(object):
        b: str
        def __init__(self, b: str) -> None: ...
      class C(A, B):
        c: int
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
      from typing import Any
      attr: module
      class Foo(Any):
        a: int
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
      class Foo(object):
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
      from typing import Any
      attr: module
      class Foo(object):
        a: int
        b: int
        c: str
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
      class Foo(object):
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
      from typing import Any
      attr: module
      class Foo(object):
        a: int
        b: Any
        c: str
        def __init__(self, a: int = ..., b = ..., c: str = ...) -> None: ...
        def default_b(self) -> int: ...
        def default_c(self) -> Any: ...
    """)

  def test_repeated_default(self):
    # Regression test for a bug where `params` and `calls` shared an underlying
    # list object, so modifying one affected the type of the other.
    self.Check("""
      import attr

      class Call(object):
        pass

      @attr.s
      class Function(object):
        params = attr.ib(factory=list)
        calls = attr.ib(factory=list)

      class FunctionMap(object):

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
      from typing import Any, List
      attr: module
      FACTORIES: List[nothing]
      class Foo:
        x: Any
        def __init__(self, x = ...) -> None: ...
    """)


class TestAttrs(test_base.TargetIndependentTest):
  """Tests for attr.s."""

  def setUp(self):
    super().setUp()
    # Checking field defaults against their types should work even when general
    # variable checking is disabled.
    self.options.tweak(check_variable_types=False)

  def test_basic(self):
    ty = self.Infer("""
      import attr
      @attr.s()
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
        def __init__(self, x, y: int, z: str) -> None: ...
    """)

  def test_no_init(self):
    ty = self.Infer("""
      import attr
      @attr.s(init=False)
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

test_base.main(globals(), __name__ == "__main__")
