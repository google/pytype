"""Tests for classes."""

from pytype.tests import test_base
from pytype.tests import test_utils


class ClassesTest(test_base.BaseTest):
  """Tests for classes."""

  def test_class_getitem(self):
    ty = self.Infer("""
      class A(type):
        def __getitem__(self, i):
          return 42
      X = A("X", (object,), {})
      v = X[0]
    """)
    self.assertTypesMatchPytd(ty, """
      class A(type):
        def __getitem__(self, i) -> int: ...
      class X(object, metaclass=A): ...
      v = ...  # type: int
    """)

  def test_new_annotated_cls(self):
    ty = self.Infer("""
      from typing import Type
      class Foo:
        def __new__(cls: Type[str]):
          return super(Foo, cls).__new__(cls)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class Foo:
        def __new__(cls: Type[str]) -> str: ...
    """)

  def test_recursive_constructor(self):
    self.Check("""
      from typing import List
      MyType = List['Foo']
      class Foo:
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
        def Convert(self):
          self.x
    """)

  def test_recursive_constructor_attribute(self):
    self.Check("""
      from typing import List
      MyType = List['Foo']
      class Foo:
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
          self.x[0].x
    """)

  def test_recursive_constructor_bad_attribute(self):
    _, errors = self.InferWithErrors("""
      from typing import List
      MyType = List['Foo']
      class Foo:
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
        def Convert(self):
          self.y  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"y.*Foo"})

  def test_recursive_constructor_subclass(self):
    self.Check("""
      from typing import List
      MyType = List['Foo']
      class Foo:
        def __init__(self, x):
          self.Create(x)
        def Create(self, x):
          self.x = x
      class FooChild(Foo):
        def Create(self, x: MyType):
          super(FooChild, self).Create(x)
        def Convert(self):
          self.x
    """)

  def test_name_exists(self):
    self.Check("""
      from typing import Optional
      class Foo: pass
      class Bar:
        @staticmethod
        def Create(x: Optional[Foo] = None):
          return Bar(x)
        @staticmethod
        def bar():
          for name in __any_object__:
            Bar.Create()
            name
        def __init__(self, x: Optional[Foo]): pass
    """)

  def test_inherit_from_generic_class(self):
    ty = self.Infer("""
      from typing import List
      class Foo(List[str]): ...
      v = Foo()[0]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo(List[str]): ...
      v = ...  # type: str
    """)

  def test_make_generic_class(self):
    ty = self.Infer("""
      from typing import List, TypeVar, Union
      T1 = TypeVar("T1")
      T2 = TypeVar("T2")
      class Foo(List[Union[T1, T2]]): ...
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, TypeVar, Union
      T1 = TypeVar("T1")
      T2 = TypeVar("T2")
      class Foo(List[Union[T1, T2]]): ...
    """)

  def test_make_generic_class_with_concrete_value(self):
    ty = self.Infer("""
      from typing import Dict, TypeVar
      V = TypeVar("V")
      class Foo(Dict[str, V]): ...
      for v in Foo().keys():
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, TypeVar
      V = TypeVar("V")
      class Foo(Dict[str, V]): ...
      v = ...  # type: str
    """)

  def test_generic_reinstantiated(self):
    """Makes sure the result of foo.f() isn't used by both a() and b()."""
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", "def f() -> list: ...")
      self.Check("""
        import foo
        from typing import List
        def a() -> List[str]:
          x = foo.f()
          x.append("hello")
          return x
        def b() -> List[int]:
          return [x for x in foo.f()]
        """, pythonpath=[d.path])

  def test_base_init(self):
    errors = self.CheckWithErrors("""
      from typing import Sequence
      class X:
        def __init__(self, obj: Sequence):
          pass
      class Y(X):
        def __init__(self, obj: int):
          X.__init__(self, obj)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Sequence.*int"})

  def test_parameterized_class_binary_operator(self):
    self.InferWithErrors("""
      from typing import Sequence
      def f(x: Sequence[str], y: Sequence[str]) -> None:
        a = x + y  # unsupported-operands
      """)

  def test_instance_attribute(self):
    ty = self.Infer("""
      class Foo:
        def __init__(self) -> None:
          self.bar = 42
    """, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        bar: int
        def __init__(self) -> None: ...
    """)

  def test_generic_super(self):
    self.Check("""
      from typing import Callable, Generic, TypeVar
      T = TypeVar('T')
      Func = Callable[[T], str]
      class Foo(Generic[T]):
        def __init__(self, func: Func = str) -> None:
          super(Foo, self).__init__()
          self._func = func
        def f(self, value: T) -> str:
          return self._func(value)
    """)

  def test_class_containing_itself(self):
    ty = self.Infer("""
      from typing import Type
      class MyMetaclass(type):
        pass
      class MyClass(metaclass=MyMetaclass):
        my_object = None  # type: Type['MyClass']
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class MyMetaclass(type): ...
      class MyClass(metaclass=MyMetaclass):
        my_object: Type[MyClass]
    """)

  def test_decorated_class(self):
    self.CheckWithErrors("""
      from typing import Any
      def decorate(cls) -> Any:
        return cls
      @decorate
      class Foo:
        def f(self):
          return self.nonsense  # attribute-error
    """)

  def test_callable_attribute(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        class Foo:
          x: Callable[[int], int]
      """)
      self.Check("""
        import foo
        from typing import Callable, Tuple
        class Bar:
          x: Callable[[int], int]
          y: Callable[[int], int] = lambda i: i
          def __init__(self, z: Callable[[int], int]):
            self.z = z
          def f(self) -> Tuple[int, int, int, int]:
            return self.x(0), self.y(0), self.z(0), foo.Foo().x(0)
      """, pythonpath=[d.path])

  def test_nested_class_init(self):
    ty = self.Infer("""
      class Foo:
        class Bar:
          def __init__(self):
            self.x = 0
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        class Bar:
          x: int
          def __init__(self) -> None: ...
    """)

  def test_new_and_subclass(self):
    ty = self.Infer("""
      class Foo:
        def __new__(cls) -> 'Foo':
          return cls()
      class Bar(Foo):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      _TFoo = TypeVar('_TFoo', bound=Foo)
      class Foo:
        def __new__(cls: type[_TFoo]) -> _TFoo: ...
      class Bar(Foo): ...
    """)


class ClassesTestPython3Feature(test_base.BaseTest):
  """Tests for classes."""

  def test_class_starargs(self):
    ty = self.Infer("""
      class Foo: pass
      class Bar: pass
      bases = (Foo, Bar)
      class Baz(*bases): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Type
      bases: Tuple[Type[Foo], Type[Bar]]
      class Foo: ...
      class Bar: ...
      class Baz(Foo, Bar): ...
    """)

  def test_class_kwargs(self):
    ty = self.Infer("""
      # x, y are passed to type() or the metaclass. We currently ignore them.
      class Thing(x=True, y="foo"): pass
    """)
    self.assertTypesMatchPytd(ty, """
    class Thing: ...
    """)

  def test_metaclass_kwarg(self):
    self.Check("""
      import abc
      class Example(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def foo(self) -> int:
          return None
    """)

  def test_class_starargs_with_metaclass(self):
    self.Check("""
      class Foo: pass
      class Bar: pass
      bases = (Foo, Bar)
      class Baz(*bases, metaclass=type): pass
    """)

  def test_build_class_quick(self):
    # A() hits maximum stack depth
    ty = self.Infer("""
      def f():
        class A: pass
        return {A: A()}
    """, quick=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict: ...
    """)

  def test_type_change(self):
    ty = self.Infer("""
      class A:
        def __init__(self):
          self.__class__ = int
      x = "" % type(A())
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        def __init__(self) -> None: ...
      x = ...  # type: str
    """)

  def test_ambiguous_base_class(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        class Foo(Any): ...
      """)
      self.Check("""
        from typing import Tuple
        import foo
        def f() -> Tuple[int]:
          return foo.Foo()
      """, pythonpath=[d.path])

  def test_callable_inheritance(self):
    self.Check("""
      from typing import Callable
      Foo = Callable[[], None]
      class Bar(Foo):
        def __call__(self):
          pass
      def f(x: Foo):
        pass
      f(Bar(__any_object__, __any_object__))
    """)

  def test_init_test_class_in_setup(self):
    ty = self.Infer("""
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      class A(unittest.case.TestCase):
          x = ...  # type: int
          def fooTest(self) -> int: ...
          def setUp(self) -> None : ...
    """)

  def test_init_inherited_test_class_in_setup(self):
    ty = self.Infer("""
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
      class B(A):
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      class A(unittest.case.TestCase):
          x = ...  # type: int
          def setUp(self) -> None : ...
      class B(A):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)

  def test_init_test_class_in_init_and_setup(self):
    ty = self.Infer("""
      import unittest
      class A(unittest.TestCase):
        def __init__(self, foo: str):
          self.foo = foo
        def setUp(self):
          self.x = 10
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      class A(unittest.case.TestCase):
          x = ...  # type: int
          foo = ...  # type: str
          def __init__(self, foo: str) -> NoneType: ...
          def fooTest(self) -> int: ...
          def setUp(self) -> None : ...
    """)

  def test_set_metaclass(self):
    ty = self.Infer("""
      class A(type):
        def f(self):
          return 3.14
      class X(metaclass=A):
        pass
      v = X.f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        def f(self) -> float: ...
      class X(metaclass=A):
        pass
      v = ...  # type: float
    """)

  def test_no_metaclass(self):
    # In this case, the metaclass should not actually be set.
    ty = self.Infer("""
      class X(metaclass=type):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      class X:
        pass
    """)

  def test_metaclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class MyMeta(type):
          def register(self, cls: type) -> None: ...
        def mymethod(funcobj: T) -> T: ...
      """)
      ty = self.Infer("""
        import foo
        class X(metaclass=foo.MyMeta):
          @foo.mymethod
          def f(self):
            return 42
        X.register(tuple)
        v = X().f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Type
        class X(metaclass=foo.MyMeta):
          def f(self) -> int: ...
        v = ...  # type: int
      """)

  @test_base.skip("Setting metaclass to a function doesn't work yet.")
  def test_function_as_metaclass(self):
    ty = self.Infer("""
      def MyMeta(name, bases, members):
        return type(name, bases, members)
      class X(metaclass=MyMeta):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def MyMeta(names, bases, members) -> Any: ...
      class X(metaclass=MyMeta):
        pass
    """)

  def test_unknown_metaclass(self):
    self.Check("""
      class Foo(metaclass=__any_object__):
        def foo(self):
          self.bar()
        @classmethod
        def bar(cls):
          pass
    """)

  def test_py2_metaclass(self):
    errors = self.CheckWithErrors("""
      import abc
      class Foo:  # ignored-metaclass[e]
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def f(self) -> int: ...
    """)
    self.assertErrorRegexes(errors, {"e": r"abc\.ABCMeta.*Foo"})

  def test_new_no_bases(self):
    self.Check("""
      class Foo:
        def __new__(cls, x):
          self = super().__new__(cls)
          self.x = x
          return self
      Foo(0)
    """)

  def test_new_pyi_no_bases(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo:
          def __new__(cls, x) -> Foo: ...
      """)
      self.Check("""
        import foo
        foo.Foo(0)
      """, pythonpath=[d.path])

  def test_type_subclass(self):
    self.Check("""
      class A(type):
        def __init__(self, name, bases, dct):
          super().__init__(name, bases, dct)
      class B(type, metaclass=A):
        pass
    """)

  def test_attribute_in_decorated_init(self):
    self.Check("""
      from typing import Any
      def decorate(f) -> Any:
        return f
      class X:
        @decorate
        def __init__(self):
          self.x = 0
      x = X()
      assert_type(x.x, int)
    """)

  def test_attribute_in_decorated_init_inference(self):
    ty = self.Infer("""
      from typing import Any
      def decorate(f) -> Any:
        return f
      class X:
        @decorate
        def __init__(self):
          self.x = 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def decorate(f) -> Any: ...
      class X:
        __init__: Any
        x: int
    """)

  def test_init_subclass_super(self):
    self.Check("""
      class A:
        def __init_subclass__(cls):
          pass
      class B(A):
        def __init_subclass__(cls):
          super().__init_subclass__()
    """)

  def test_init_subclass_explicit_classmethod(self):
    ty = self.Infer("""
      class Foo:
        @classmethod
        def __init_subclass__(cls):
          pass
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo:
        def __init_subclass__(cls) -> None: ...
    """)


if __name__ == "__main__":
  test_base.main()
