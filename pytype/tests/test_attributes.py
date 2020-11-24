"""Test instance and class attributes."""

from pytype import file_utils
from pytype.tests import test_base


class TestStrictNone(test_base.TargetIndependentTest):
  """Tests for strict attribute checking on None."""

  def test_module_constant(self):
    self.Check("""
      x = None
      def f():
        return x.upper()
    """)

  def test_class_constant(self):
    self.Check("""
      class Foo(object):
        x = None
        def f(self):
          return self.x.upper()
    """)

  def test_class_constant_error(self):
    errors = self.CheckWithErrors("""
      x = None
      class Foo(object):
        x = x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_multiple_paths(self):
    errors = self.CheckWithErrors("""
      x = None
      def f():
        z = None if __random__ else x
        y = z
        return y.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_late_initialization(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.x = None
        def f(self):
          return self.x.upper()
        def set_x(self):
          self.x = ""
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Optional
      class Foo(object):
        x = ...  # type: Optional[str]
        def __init__(self) -> None: ...
        def f(self) -> Any: ...
        def set_x(self) -> None: ...
    """)

  def test_pyi_constant(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: None
      """)
      self.Check("""
        import foo
        def f():
          return foo.x.upper()
      """, pythonpath=[d.path])

  def test_pyi_attribute(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          x = ...  # type: None
      """)
      self.Check("""
        import foo
        def f():
          return foo.Foo.x.upper()
      """, pythonpath=[d.path])

  def test_return_value(self):
    errors = self.CheckWithErrors("""
      def f():
        pass
      def g():
        return f().upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_method_return_value(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def f(self):
          pass
      def g():
        return Foo().f().upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_pyi_return_value(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "def f() -> None: ...")
      errors = self.CheckWithErrors("""
        import foo
        def g():
          return foo.f().upper()  # attribute-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_pass_through_none(self):
    errors = self.CheckWithErrors("""
      def f(x):
        return x
      def g():
        return f(None).upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_shadowed_local_origin(self):
    self.Check("""
      x = None
      def f():
        y = None
        y = "hello"
        return x if __random__ else y
      def g():
        return f().upper()
    """)

  @test_base.skip("has_strict_none_origins can't tell if an origin is blocked.")
  def test_blocked_local_origin(self):
    self.Check("""
      x = None
      def f():
        v = __random__
        if v:
          y = None
        return x if v else y
      def g():
        return f().upper()
    """)

  def test_return_constant(self):
    self.Check("""
      x = None
      def f():
        return x
      def g():
        return f().upper()
    """)

  def test_unpacked_none(self):
    errors = self.CheckWithErrors("""
      _, a = 42, None
      b = a.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def test_function_default(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(self, v=None):
          v.upper()  # attribute-error[e]
      def f():
        Foo()
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None.*traceback.*line 5"})

  def test_keep_none_return(self):
    ty = self.Infer("""
      def f():
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> None: ...
    """)

  def test_keep_none_yield(self):
    ty = self.Infer("""
      def f():
        yield None
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Any
      def f() -> Generator[None, Any, None]: ...
    """)

  def test_keep_contained_none_return(self):
    ty = self.Infer("""
      def f():
        return [None]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f() -> List[None]: ...
    """)

  def test_discard_none_return(self):
    ty = self.Infer("""
      x = None
      def f():
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: None
      def f() -> Any: ...
    """)

  def test_discard_none_yield(self):
    ty = self.Infer("""
      x = None
      def f():
        yield x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      x = ...  # type: None
      def f() -> Generator[Any, Any, None]: ...
    """)

  def test_discard_contained_none_return(self):
    ty = self.Infer("""
      x = None
      def f():
        return [x]
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: None
      def f() -> list: ...
    """)

  def test_discard_attribute_none_return(self):
    ty = self.Infer("""
      class Foo:
        x = None
      def f():
        return Foo.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo:
        x = ...  # type: None
      def f() -> Any: ...
    """)

  def test_getitem(self):
    errors = self.CheckWithErrors("""
      def f():
        x = None
        return x[0]  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"item retrieval.*None.*int"})

  def test_ignore_getitem(self):
    self.Check("""
      x = None
      def f():
        return x[0]
    """)

  def test_ignore_iter(self):
    self.Check("""
      x = None
      def f():
        return [y for y in x]
    """)

  def test_contains(self):
    errors = self.CheckWithErrors("""
      def f():
        x = None
        return 42 in x  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"'in'.*None.*int"})

  def test_ignore_contains(self):
    self.Check("""
      x = None
      def f():
        return 42 in x
    """)

  def test_property(self):
    self.Check("""
      class Foo(object):
        def __init__(self):
          self._dofoo = __random__
        @property
        def foo(self):
          return "hello" if self._dofoo else None
      foo = Foo()
      if foo.foo:
        foo.foo.upper()
    """)

  def test_isinstance(self):
    self.Check("""
      class Foo(object):
        def f(self):
          instance = None if __random__ else {}
          if instance is not None:
            self.g(instance)
        def g(self, instance):
          if isinstance(instance, str):
            instance.upper()  # line 10
    """)

  def test_impossible_return_type(self):
    self.Check("""
      from typing import Dict
      def f():
        d = None  # type: Dict[str, str]
        instance = d.get("hello")
        return instance if instance else "world"
      def g():
        return f().upper()
    """)

  def test_no_return(self):
    self.Check("""
      def f():
        text_value = "hello" if __random__ else None
        if not text_value:
          missing_value()
        return text_value.strip()
      def missing_value():
        raise ValueError()
    """)


class TestAttributes(test_base.TargetIndependentTest):
  """Tests for attributes."""

  def test_simple_attribute(self):
    ty = self.Infer("""
      class A(object):
        def method1(self):
          self.a = 3
        def method2(self):
          self.a = 3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A(object):
        a = ...  # type: Union[complex, int]
        def method1(self) -> NoneType: ...
        def method2(self) -> NoneType: ...
    """)

  def test_outside_attribute_access(self):
    ty = self.Infer("""
      class A(object):
        pass
      def f1():
        A().a = 3
      def f2():
        A().a = 3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class A(object):
        a = ...  # type: Union[complex, int]
      def f1() -> NoneType: ...
      def f2() -> NoneType: ...
    """)

  def test_private(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self._x = 3
        def foo(self):
          return self._x
    """)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        _x = ...  # type: int
        def __init__(self) -> None: ...
        def foo(self) -> int: ...
    """)

  def test_public(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self.x = 3
        def foo(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        x = ...  # type: int
        def __init__(self) -> None: ...
        def foo(self) -> int: ...
    """)

  def test_crosswise(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          if id(self):
            self.b = B()
        def set_on_b(self):
          self.b.x = 3
      class B(object):
        def __init__(self):
          if id(self):
            self.a = A()
        def set_on_a(self):
          self.a.x = 3j
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        b = ...  # type: B
        x = ...  # type: complex
        def __init__(self) -> None: ...
        def set_on_b(self) -> NoneType: ...
      class B(object):
        a = ...  # type: A
        x = ...  # type: int
        def __init__(self) -> None: ...
        def set_on_a(self) -> NoneType: ...
    """)

  def test_attr_with_bad_getattr(self):
    self.Check("""
      class AttrA(object):
        def __getattr__(self, name2):
          pass
      class AttrB(object):
        def __getattr__(self):
          pass
      class AttrC(object):
        def __getattr__(self, x, y):
          pass
      class Foo(object):
        A = AttrA
        B = AttrB
        C = AttrC
        def foo(self):
          self.A
          self.B
          self.C
    """)

  def test_inherit_getattribute(self):
    ty = self.Infer("""
      class MyClass1(object):
        def __getattribute__(self, name):
          return super(MyClass1, self).__getattribute__(name)

      class MyClass2(object):
        def __getattribute__(self, name):
          return object.__getattribute__(self, name)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class MyClass1(object):
        def __getattribute__(self, name) -> Any: ...
      class MyClass2(object):
        def __getattribute__(self, name) -> Any: ...
    """)

  def test_getattribute(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return 42
      a = A()
      a.x = "hello world"
      x = a.x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
        def __getattribute__(self, name) -> int: ...
      a = ...  # type: A
      x = ...  # type: int
    """)

  def test_getattribute_branch(self):
    ty = self.Infer("""
      class A(object):
        x = "hello world"
      class B(object):
        def __getattribute__(self, name):
          return False
      def f(x):
        v = A()
        if x:
          v.__class__ = B
        return v.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        x = ...  # type: str
      class B(object):
        def __getattribute__(self, name) -> bool: ...
      def f(x) -> Any: ...
    """)

  def test_set_class(self):
    ty = self.Infer("""
      def f(x):
        y = None
        y.__class__ = x.__class__
        return set([x, y])
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> set: ...
    """)

  def test_get_mro(self):
    ty = self.Infer("""
      x = int.mro()
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: list
    """)

  def test_call(self):
    ty = self.Infer("""
      class A(object):
        def __call__(self):
          return 42
      x = A()()
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __call__(self) -> int: ...
      x = ...  # type: int
    """)

  @test_base.skip("Magic methods aren't computed")
  def test_call_computed(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return int
      x = A().__call__()
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __getattribute__(self, name) -> int: ...
      x = ...  # type: int
    """)

  def test_has_dynamic_attributes(self):
    self.Check("""
      class Foo1(object):
        has_dynamic_attributes = True
      class Foo2(object):
        HAS_DYNAMIC_ATTRIBUTES = True
      class Foo3(object):
        _HAS_DYNAMIC_ATTRIBUTES = True
      Foo1().baz
      Foo2().baz
      Foo3().baz
    """)

  def test_has_dynamic_attributes_subclass(self):
    self.Check("""
      class Foo(object):
        _HAS_DYNAMIC_ATTRIBUTES = True
      class Bar(Foo):
        pass
      Foo().baz
      Bar().baz
    """)

  def test_has_dynamic_attributes_class_attr(self):
    # Only instance attributes are dynamic.
    errors = self.CheckWithErrors("""
      class Foo(object):
        _HAS_DYNAMIC_ATTRIBUTES = True
      Foo.CONST  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"CONST.*Foo"})

  def test_has_dynamic_attributes_metaclass(self):
    # Since class attributes of Foo are instance attributes for the metaclass,
    # both class and instance attributes of Foo are now dynamic.
    self.Check("""
      import six
      class Metaclass(type):
        _HAS_DYNAMIC_ATTRIBUTES = True
      class Foo(six.with_metaclass(Metaclass, object)):
        pass
      @six.add_metaclass(Metaclass)
      class Bar(object):
        pass
      Foo.CONST
      Foo().baz
      Bar.CONST
      Bar().baz
    """)

  def test_has_dynamic_attributes_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Foo(object):
          has_dynamic_attributes = True
      """)
      self.Check("""
        import mod
        mod.Foo().baz
      """, pythonpath=[d.path])

  def test_has_dynamic_attributes_metaclass_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("mod.pyi", """
        class Metaclass(type):
          _HAS_DYNAMIC_ATTRIBUTES: bool
        class Foo(metaclass=Metaclass): ...
      """)
      self.Check("""
        import mod
        class Bar(mod.Foo):
          pass
        mod.Foo.CONST
        mod.Foo().baz
        Bar.CONST
        Bar().baz
      """, pythonpath=[d.path])

  def test_attr_on_static_method(self):
    self.Check("""
      import collections

      X = collections.namedtuple("X", "a b")
      X.__new__.__defaults__ = (1, 2)
      """)

  def test_module_type_attribute(self):
    self.Check("""
      import types
      v = None  # type: types.ModuleType
      v.some_attribute
    """)

  def test_attr_on_none(self):
    self.InferWithErrors("""
      def f(arg):
        x = "foo" if arg else None
        if not x:
          x.upper()  # attribute-error
    """)

  def test_iterator_on_none(self):
    self.InferWithErrors("""
      def f():
        pass
      a, b = f()  # attribute-error
    """)

  def test_overloaded_builtin(self):
    self.Check("""
      if __random__:
        getattr = None
      else:
        getattr(__any_object__, __any_object__)
    """)

  def test_callable_return(self):
    self.Check("""
      from typing import Callable
      class Foo(object):
        def __init__(self):
          self.x = 42
      v = None  # type: Callable[[], Foo]
      w = v().x
    """)

  def test_property_on_union(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.foo = 1
      class B(object):
        def __init__(self):
          self.bar = 2
        @property
        def foo(self):
          return self.bar
      x = A() if __random__ else B()
      a = x.foo
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      x = ...  # type: Union[A, B]
      class A:
        foo = ...  # type: int
        def __init__(self) -> None: ...
      class B:
        bar = ...  # type: int
        foo = ...  # type: int
        def __init__(self) -> None: ...
    """)

  @test_base.skip("Needs vm._get_iter() to iterate over individual bindings.")
  def test_bad_iter(self):
    errors = self.CheckWithErrors("""
      v = [] if __random__ else 42
      for _ in v:  # attribute-error[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*int"})

  def test_bad_getitem(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __getitem__(self, x):
          return 0
      v = Foo() if __random__ else 42
      for _ in v:  # attribute-error[e]
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__.*int.*Union\[Foo, int\]"})

  def test_bad_contains(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __iter__(self):
          return iter([])
      v = Foo() if __random__ else 42
      if 42 in v:  # unsupported-operands[e]
        pass
    """)
    self.assertErrorRegexes(
        errors, {"e": r"'in'.*'Union\[Foo, int\]' and 'int'"})

  def test_subclass_shadowing(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X:
          b = ...  # type: int
        """)
      self.Check("""
        import foo
        a = foo.X()
        a.b  # The attribute exists
        if __random__:
          a.b = 1  # A new value is assigned
        else:
          a.b  # The original attribute isn't overwritten by the assignment
        """, pythonpath=[d.path])

  def test_generic_property(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, Optional, TypeVar
        T = TypeVar("T")
        class Foo(Generic[T]):
          @property
          def x(self) -> Optional[T]: ...
        def f() -> Foo[str]: ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.f().x
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      from typing import Optional
      foo: module
      def f() -> Optional[str]: ...
    """)

  def test_bad_instance_assignment(self):
    errors = self.CheckWithErrors("""
      class Foo:
        x = None  # type: int
        def foo(self):
          self.x = 'hello, world'  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_bad_cls_assignment(self):
    errors = self.CheckWithErrors("""
      class Foo:
        x = None  # type: int
      Foo.x = 'hello, world'  # annotation-type-mismatch[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_any_annotation(self):
    self.Check("""
      from typing import Any
      class Foo:
        x = None  # type: Any
        def foo(self):
          print(self.x.some_attr)
          self.x = 0
          print(self.x.some_attr)
    """)

  def test_preserve_annotation_in_pyi(self):
    ty = self.Infer("""
      class Foo:
        x = None  # type: float
        def __init__(self):
          self.x = 0
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: float
        def __init__(self) -> None: ...
    """)

  def test_annotation_in_init(self):
    ty, errors = self.InferWithErrors("""
      class Foo:
        def __init__(self):
          self.x = 0  # type: int
        def oops(self):
          self.x = ''  # annotation-type-mismatch[e]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        x: int
        def __init__(self) -> None: ...
        def oops(self) -> None: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"Annotation: int.*Assignment: str"})

  def test_split(self):
    ty = self.Infer("""
      from typing import Union
      class Foo:
        pass
      class Bar:
        pass
      def f(x):
        # type: (Union[Foo, Bar]) -> None
        if isinstance(x, Foo):
          x.foo = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo:
        foo: int
      class Bar: ...
      def f(x: Union[Foo, Bar]) -> None: ...
    """)

  def test_separate_instances(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        _T = TypeVar('_T')

        class Foo:
          return_value: Any

        def patch() -> Foo: ...
      """)
      self.Check("""
        import foo

        x = foo.patch()
        y = foo.patch()

        x.return_value = 0
        y.return_value.rumpelstiltskin = 1
      """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
