"""Tests for classes."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class ClassesTest(test_base.TargetIndependentTest):
  """Tests for classes."""

  def test_make_class(self):
    ty = self.Infer("""
      class Thing(tuple):
        def __init__(self, x):
          self.x = x
      def f():
        x = Thing(1)
        x.y = 3
        return x
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    class Thing(tuple):
      x = ...  # type: Any
      y = ...  # type: int
      def __init__(self, x) -> NoneType: ...
    def f() -> Thing: ...
    """)

  def test_load_classderef(self):
    """Exercises the Python 3 LOAD_CLASSDEREF opcode.

    Serves as a simple test for Python 2.
    """
    self.Check("""
      class A(object):
        def foo(self):
          x = 10
          class B(object):
            y = str(x)
    """)

  def test_class_decorator(self):
    ty = self.Infer("""
      @__any_object__
      class MyClass(object):
        def method(self, response):
          pass
      def f():
        return MyClass()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      MyClass = ...  # type: Any
      def f() -> Any: ...
    """)

  def test_class_name(self):
    ty = self.Infer("""
      class MyClass(object):
        def __init__(self, name):
          pass
      def f():
        factory = MyClass
        return factory("name")
      f()
    """, deep=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
    class MyClass(object):
      def __init__(self, name: str) -> NoneType: ...

    def f() -> MyClass: ...
    """)

  def test_inherit_from_unknown(self):
    ty = self.Infer("""
      class A(__any_object__):
        pass
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    class A(Any):
      pass
    """)

  def test_inherit_from_unknown_and_call(self):
    ty = self.Infer("""
      x = __any_object__
      class A(x):
        def __init__(self):
          x.__init__(self)
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    x = ...  # type: Any
    class A(Any):
      def __init__(self) -> NoneType: ...
    """)

  def test_inherit_from_unknown_and_set_attr(self):
    ty = self.Infer("""
      class Foo(__any_object__):
        def __init__(self):
          setattr(self, "test", True)
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    class Foo(Any):
      def __init__(self) -> NoneType: ...
    """)

  def test_inherit_from_unknown_and_initialize(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      class Bar(Foo, __any_object__):
        pass
      x = Bar(duration=0)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        pass
      class Bar(Foo, Any):
        pass
      x = ...  # type: Bar
    """)

  def test_inherit_from_unsolvable(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any: ...
      """)
      ty = self.Infer("""
        import a
        class Foo(object):
          pass
        class Bar(Foo, a.A):
          pass
        x = Bar(duration=0)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        class Foo(object):
          pass
        class Bar(Foo, Any):
          pass
        x = ...  # type: Bar
      """)

  def test_classmethod(self):
    ty = self.Infer("""
      module = __any_object__
      class Foo(object):
        @classmethod
        def bar(cls):
          module.bar("", '%Y-%m-%d')
      def f():
        return Foo.bar()
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import Any
    module = ...  # type: Any
    def f() -> NoneType: ...
    class Foo(object):
      @classmethod
      def bar(cls) -> None: ...
    """)

  def test_factory_classmethod(self):
    ty = self.Infer("""
      class Foo(object):
        @classmethod
        def factory(cls, *args, **kwargs):
          return object.__new__(cls)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      _TFoo = TypeVar('_TFoo', bound=Foo)
      class Foo:
        @classmethod
        def factory(cls: Type[_TFoo], *args, **kwargs) -> _TFoo: ...
    """)

  def test_classmethod_return_inference(self):
    ty = self.Infer("""
      class Foo(object):
        A = 10
        @classmethod
        def bar(cls):
          return cls.A
    """)
    self.assertTypesMatchPytd(ty, """
    class Foo(object):
      A: int
      @classmethod
      def bar(cls) -> int: ...
    """)

  def test_inherit_from_unknown_attributes(self):
    ty = self.Infer("""
      class Foo(__any_object__):
        def f(self):
          self.x = [1]
          self.y = list(self.x)
    """)
    self.assertTypesMatchPytd(ty, """
    from typing import List
    from typing import Any
    class Foo(Any):
      x = ...  # type: List[int, ...]
      y = ...  # type: List[int, ...]
      def f(self) -> NoneType: ...
    """)

  def test_inner_class(self):
    ty = self.Infer("""
      def f():
        class Foo(object):
          x = 3
        l = Foo()
        return l.x
    """, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_super(self):
    ty = self.Infer("""
      class Base(object):
        def __init__(self, x, y):
          pass
      class Foo(Base):
        def __init__(self, x):
          super(Foo, self).__init__(x, y='foo')
    """)
    self.assertTypesMatchPytd(ty, """
    class Base(object):
      def __init__(self, x, y) -> NoneType: ...
    class Foo(Base):
      def __init__(self, x) -> NoneType: ...
    """)

  def test_super_error(self):
    _, errors = self.InferWithErrors("""
      class Base(object):
        def __init__(self, x, y, z):
          pass
      class Foo(Base):
        def __init__(self, x):
          super(Foo, self).__init__()  # missing-parameter[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"x"})

  def test_super_in_init(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 3

      class B(A):
        def __init__(self):
          super(B, self).__init__()

        def get_x(self):
          return self.x
    """, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
        class A(object):
          x = ...  # type: int
          def __init__(self) -> None: ...

        class B(A):
          x = ...  # type: int
          def get_x(self) -> int: ...
          def __init__(self) -> None: ...
    """)

  def test_super_diamond(self):
    ty = self.Infer("""
      class A(object):
        x = 1
      class B(A):
        y = 4
      class C(A):
        y = "str"
        z = 3j
      class D(B, C):
        def get_x(self):
          return super(D, self).x
        def get_y(self):
          return super(D, self).y
        def get_z(self):
          return super(D, self).z
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
          x = ...  # type: int
      class B(A):
          y = ...  # type: int
      class C(A):
          y = ...  # type: str
          z = ...  # type: complex
      class D(B, C):
          def get_x(self) -> int: ...
          def get_y(self) -> int: ...
          def get_z(self) -> complex: ...
    """)

  def test_inherit_from_list(self):
    ty = self.Infer("""
      class MyList(list):
        def foo(self):
          return getattr(self, '__str__')
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class MyList(list):
        def foo(self) -> Any: ...
    """)

  def test_class_attr(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      OtherFoo = Foo().__class__
      Foo.x = 3
      OtherFoo.x = "bar"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        x = ...  # type: str
      OtherFoo = Foo
    """)

  def test_call_class_attr(self):
    ty = self.Infer("""
      class Flag(object):
        convert_method = int
        def convert(self, value):
          return self.convert_method(value)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class Flag(object):
        convert_method = ...  # type: Type[int]
        def convert(self, value) -> int: ...
    """)

  def test_bound_method(self):
    ty = self.Infer("""
      class Random(object):
          def seed(self):
            pass

      _inst = Random()
      seed = _inst.seed
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      class Random(object):
         def seed(self) -> None: ...

      _inst = ...  # type: Random
      def seed() -> None: ...
    """)

  def test_mro_with_unsolvables(self):
    ty = self.Infer("""
      from nowhere import X, Y  # pytype: disable=import-error
      class Foo(Y):
        pass
      class Bar(X, Foo, Y):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
      Y = ...  # type: Any
      class Foo(Any):
        ...
      class Bar(Any, Foo, Any):
        ...
    """)

  def test_property(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self._name = "name"
        def test(self):
          return self.name
        name = property(fget=lambda self: self._name)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        _name = ...  # type: str
        name = ...  # type: Any
        def __init__(self) -> None: ...
        def test(self) -> str: ...
    """)

  def test_descriptor_self(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self._name = "name"
        def __get__(self, obj, objtype):
          return self._name
      class Bar(object):
        def test(self):
          return self.foo
        foo = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        _name = ...  # type: str
        def __init__(self) -> None: ...
        def __get__(self, obj, objtype) -> str: ...
      class Bar(object):
        foo = ...  # type: str
        def test(self) -> str: ...
    """)

  def test_descriptor_instance(self):
    ty = self.Infer("""
      class Foo(object):
        def __get__(self, obj, objtype):
          return obj._name
      class Bar(object):
        def __init__(self):
          self._name = "name"
        def test(self):
          return self.foo
        foo = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        def __get__(self, obj, objtype) -> Any: ...
      class Bar(object):
        _name = ...  # type: str
        foo = ...  # type: Any
        def __init__(self) -> None: ...
        def test(self) -> str: ...
    """)

  def test_descriptor_class(self):
    ty = self.Infer("""
      class Foo(object):
        def __get__(self, obj, objtype):
          return objtype._name
      class Bar(object):
        def test(self):
          return self.foo
        _name = "name"
        foo = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        def __get__(self, obj, objtype) -> Any: ...
      class Bar(object):
        _name = ...  # type: str
        foo = ...  # type: Any
        def test(self) -> str: ...
    """)

  def test_bad_descriptor(self):
    ty = self.Infer("""
      class Foo(object):
        __get__ = None
      class Bar(object):
        foo = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        __get__ = ...  # type: None
      class Bar(object):
        foo = ...  # type: Any
    """)

  def test_not_descriptor(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      foo = Foo()
      foo.__get__ = None
      class Bar(object):
        foo = foo
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        __get__ = ...  # type: None
      foo = ...  # type: Foo
      class Bar(object):
        foo = ...  # type: Foo
    """)

  def test_getattr(self):
    ty = self.Infer("""
      class Foo(object):
        def __getattr__(self, name):
          return "attr"
      def f():
        return Foo().foo
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __getattr__(self, name) -> str: ...
      def f() -> str: ...
    """)

  def test_getattr_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __getattr__(self, name) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.Foo().foo
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> str: ...
      """)

  def test_getattribute(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return 42
      x = A().x
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __getattribute__(self, name) -> int: ...
      x = ...  # type: int
    """)

  def test_getattribute_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __getattribute__(self, name) -> int: ...
      """)
      ty = self.Infer("""
        import a
        x = a.A().x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def test_inherit_from_classobj(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A():
          pass
      """)
      ty = self.Infer("""
        import a
        class C(a.A):
          pass
        name = C.__name__
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ... # type: module
        class C(a.A):
          pass
        name = ... # type: str
      """)

  def test_metaclass_getattribute(self):
    with file_utils.Tempdir() as d:
      d.create_file("enum.pyi", """
        from typing import Any
        class EnumMeta(type):
          def __getattribute__(self, name) -> Any: ...
        class Enum(metaclass=EnumMeta): ...
        class IntEnum(int, Enum): ...
      """)
      ty = self.Infer("""
        import enum
        class A(enum.Enum):
          x = 1
        class B(enum.IntEnum):
          x = 1
        enum1 = A.x
        name1 = A.x.name
        enum2 = B.x
        name2 = B.x.name
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        enum = ...  # type: module
        class A(enum.Enum):
          x = ...  # type: int
        class B(enum.IntEnum):
          x = ...  # type: int
        enum1 = ...  # type: Any
        name1 = ...  # type: Any
        enum2 = ...  # type: Any
        name2 = ...  # type: Any
      """)

  def test_return_class_type(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type, Union
        class A(object):
          x = ...  # type: int
        class B(object):
          x = ...  # type: str
        def f(x: Type[A]) -> Type[A]: ...
        def g() -> Type[Union[A, B]]: ...
        def h() -> Type[Union[int, B]]: ...
      """)
      ty = self.Infer("""
        import a
        x1 = a.f(a.A).x
        x2 = a.g().x
        x3 = a.h().x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        a = ...  # type: module
        x1 = ...  # type: int
        x2 = ...  # type: Union[int, str]
        x3 = ...  # type: str
      """)

  def test_call_class_type(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A(object): ...
        class B(object):
          MyA = ...  # type: Type[A]
      """)
      ty = self.Infer("""
        import a
        x = a.B.MyA()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: a.A
      """)

  def test_call_alias(self):
    ty = self.Infer("""
      class A: pass
      B = A
      x = B()
    """, deep=False)
    # We don't care whether the type of x is inferred as A or B, but we want it
    # to always be the same.
    self.assertTypesMatchPytd(ty, """
      class A: ...
      B = A
      x = ...  # type: A
    """)

  def test_new(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __new__(cls, x: int) -> B: ...
        class B: ...
      """)
      ty = self.Infer("""
        import a
        class C(object):
          def __new__(cls):
            return "hello world"
        x1 = a.A(42)
        x2 = C()
        x3 = object.__new__(bool)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        class C(object):
          def __new__(cls) -> str: ...
        x1 = ...  # type: a.B
        x2 = ...  # type: str
        x3 = ...  # type: bool
      """)

  def test_new_and_init(self):
    ty = self.Infer("""
      class A(object):
        def __new__(cls, a, b):
          return super(A, cls).__new__(cls, a, b)
        def __init__(self, a, b):
          self.x = a + b
      class B(object):
        def __new__(cls, x):
          v = A(x, 0)
          v.y = False
          return v
        # __init__ should not be called
        def __init__(self, x):
          pass
      x1 = A("hello", "world")
      x2 = x1.x
      x3 = B(3.14)
      x4 = x3.x
      x5 = x3.y
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type, TypeVar
      _TA = TypeVar("_TA", bound=A)
      class A(object):
        x = ...  # type: Any
        y = ...  # type: bool
        def __new__(cls: Type[_TA], a, b) -> _TA: ...
        def __init__(self, a, b) -> None: ...
      class B(object):
        def __new__(cls, x) -> A: ...
        def __init__(self, x) -> None: ...
      x1 = ...  # type: A
      x2 = ...  # type: str
      x3 = ...  # type: A
      x4 = ...  # type: float
      x5 = ...  # type: bool
    """)

  def test_new_and_init_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        N = TypeVar("N")
        class A(Generic[T]):
          def __new__(cls, x) -> A[nothing]: ...
          def __init__(self, x: N):
            self = A[N]
        class B(object):
          def __new__(cls) -> A[str]: ...
          # __init__ should not be called
          def __init__(self, x, y) -> None: ...
      """)
      ty = self.Infer("""
        import a
        x1 = a.A(0)
        x2 = a.B()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x1 = ...  # type: a.A[int]
        x2 = ...  # type: a.A[str]
      """)

  def test_get_type(self):
    ty = self.Infer("""
      class A:
        x = 3
      def f():
        return A() if __random__ else ""
      B = type(A())
      C = type(f())
      D = type(int)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, Union
      class A:
        x = ...  # type: int
      def f() -> Union[A, str]: ...
      B = A
      C = ...  # type: Type[Union[A, str]]
      D = ...  # type: Type[type]
    """)

  def test_type_attribute(self):
    ty = self.Infer("""
      class A:
        x = 3
      B = type(A())
      x = B.x
      mro = B.mro()
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        x = ...  # type: int
      B = A
      x = ...  # type: int
      mro = ...  # type: list
    """)

  def test_type_subclass(self):
    ty = self.Infer("""
      class A(type):
        def __init__(self, name, bases, dict):
          super(A, self).__init__(name, bases, dict)
        def f(self):
          return 3.14
      Int = A(0)
      X = A("X", (int, object), {"a": 1})
      x = X()
      a = X.a
      v = X.f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        def __init__(self, name, bases, dict) -> None: ...
        def f(self) -> float: ...
      Int = ...  # type: Type[int]
      class X(int, object, metaclass=A):
        a = ...  # type: int
      x = ...  # type: X
      a = ...  # type: int
      v = ...  # type: float
    """)

  def test_union_base_class(self):
    self.Check("""
      import typing
      class A(tuple): pass
      class B(tuple): pass
      class Foo(typing.Union[A,B]): pass
      """)

  def test_metaclass_pyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(type):
          def f(self) -> float: ...
        class X(metaclass=A): ...
      """)
      ty = self.Infer("""
        import a
        v = a.X.f()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: float
      """)

  def test_unsolvable_metaclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any: ...
      """)
      d.create_file("b.pyi", """
        from a import A
        class B(metaclass=A): ...
      """)
      ty = self.Infer("""
        import b
        x = b.B.x
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        b = ...  # type: module
        x = ...  # type: Any
      """)

  def test_make_type(self):
    ty = self.Infer("""
      X = type("X", (int, object), {"a": 1})
      x = X()
      a = X.a
    """)
    self.assertTypesMatchPytd(ty, """
      class X(int, object):
        a = ...  # type: int
      x = ...  # type: X
      a = ...  # type: int
    """)

  def test_make_simple_type(self):
    ty = self.Infer("""
      X = type("X", (), {})
      x = X()
    """)
    self.assertTypesMatchPytd(ty, """
      class X(object): ...
      x = ...  # type: X
    """)

  def test_make_ambiguous_type(self):
    ty = self.Infer("""
      if __random__:
        name = "A"
      else:
        name = "B"
      X = type(name, (int, object), {"a": 1})
      x = X()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      name = ...  # type: str
      X = ...  # type: Any
      x = ...  # type: Any
    """)

  def test_type_init(self):
    ty = self.Infer("""
      import six
      class A(type):
        def __init__(self, name, bases, members):
          self.x = 42
          super(A, self).__init__(name, bases, members)
      B = A("B", (), {})
      class C(six.with_metaclass(A, object)):
        pass
      x1 = B.x
      x2 = C.x
    """)
    self.assertTypesMatchPytd(ty, """
      six: module
      class A(type):
        x: int
        def __init__(self, name, bases, members) -> None: ...
      class B(object, metaclass=A):
        x: int
      class C(object, metaclass=A):
        x: int
      x1: int
      x2: int
    """)

  def test_bad_mro_parameterized_class(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]): ...
        class B(A[T]): ...
        class C(A[T], B[T]): ...
        def f() -> C[int]: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.f()  # mro-error[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"C"})

  def test_call_parameterized_class(self):
    self.InferWithErrors("""
      from typing import List
      List[str]()  # not-callable
    """)

  def test_errorful_constructors(self):
    ty, _ = self.InferWithErrors("""
      class Foo(object):
        attr = 42
        def __new__(cls):
          return name_error  # name-error
        def __init__(self):
          self.attribute_error  # attribute-error
          self.instance_attr = self.attr
        def f(self):
          return self.instance_attr
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        attr = ...  # type: int
        instance_attr = ...  # type: int
        def __new__(cls) -> Any: ...
        def __init__(self) -> None: ...
        def f(self) -> int: ...
    """)

  def test_new_false(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls):
          return False
        def __init__(self):
          self.instance_attr = ""
        def f(self):
          return self.instance_attr
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        instance_attr = ...  # type: str
        def __new__(cls) -> bool: ...
        def __init__(self) -> None: ...
        def f(self) -> str: ...
    """)

  def test_new_ambiguous(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls):
          if __random__:
            return super(Foo, cls).__new__(cls)
          else:
            return "hello world"
        def __init__(self):
          self.instance_attr = ""
        def f(self):
          return self.instance_attr
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo(object):
        instance_attr = ...  # type: str
        def __new__(cls) -> Union[str, Foo]: ...
        def __init__(self) -> None: ...
        def f(self) -> str: ...
    """)

  def test_new_extra_arg(self):
    self.Check("""
      class Foo(object):
        def __new__(cls, _):
          return super(Foo, cls).__new__(cls)
      Foo("Foo")
    """)

  def test_new_extra_none_return(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls):
          if __random__:
            return super(Foo, cls).__new__(cls)
        def foo(self):
          return self
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar, Union
      _TFoo = TypeVar("_TFoo", bound=Foo)
      class Foo(object):
        def __new__(cls) -> Union[Foo, None]: ...
        def foo(self: _TFoo) -> _TFoo: ...
    """)

  def test_super_new_extra_arg(self):
    self.Check("""
      class Foo(object):
        def __init__(self, x):
          pass
        def __new__(cls, x):
          # The extra arg is okay because __init__ is defined.
          return super(Foo, cls).__new__(cls, x)
    """)

  def test_super_init_extra_arg(self):
    self.Check("""
      class Foo(object):
        def __init__(self, x):
          # The extra arg is okay because __new__ is defined.
          super(Foo, self).__init__(x)
        def __new__(cls, x):
          return super(Foo, cls).__new__(cls)
    """)

  def test_super_init_extra_arg2(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __new__(cls, a, b) -> Foo: ...
      """)
      self.Check("""
        import foo
        class Bar(foo.Foo):
          def __init__(self, a, b):
            # The extra args are okay because __new__ is defined on Foo.
            super(Bar, self).__init__(a, b)
      """, pythonpath=[d.path])

  def test_super_new_wrong_arg_count(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __new__(cls, x):
          return super(Foo, cls).__new__(cls, x)  # wrong-arg-count[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"1.*2"})

  def test_super_init_wrong_arg_count(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __init__(self, x):
          super(Foo, self).__init__(x)  # wrong-arg-count[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"1.*2"})

  def test_super_new_missing_parameter(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __new__(cls, x):
          # Even when __init__ is defined, too few args is an error.
          return super(Foo, cls).__new__()  # missing-parameter[e]
        def __init__(self, x):
          pass
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"cls.*__new__"})

  def test_new_kwarg(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __new__(cls):
          # ok because __init__ is defined.
          return super(Foo, cls).__new__(cls, x=42)
        def __init__(self):
          pass
      class Bar(object):
        def __new__(cls):
          return super(Bar, cls).__new__(cls, x=42)  # wrong-keyword-args[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"x.*__new__"})

  def test_init_kwarg(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __init__(self):
          # ok because __new__ is defined.
          super(Foo, self).__init__(x=42)
        def __new__(cls):
          return super(Foo, cls).__new__(cls)
      class Bar(object):
        def __init__(self):
          super(Bar, self).__init__(x=42)  # wrong-keyword-args[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"x.*__init__"})

  def test_alias_inner_class(self):
    ty = self.Infer("""
      def f():
        class Bar(object):
          def __new__(cls, _):
            return super(Bar, cls).__new__(cls)
        return Bar
      Baz = f()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type, TypeVar
      def f() -> Type[Baz]: ...
      _TBaz = TypeVar("_TBaz", bound=Baz)
      class Baz(object):
        def __new__(cls: Type[_TBaz], _) -> _TBaz: ...
    """)

  def test_module_in_class_definition_scope(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Bar: ...
      """)
      self.Check("""
        import foo
        class ConstStr(str):
          foo.Bar # testing that this does not affect inference.
          def __new__(cls, x):
            obj = super(ConstStr, cls).__new__(cls, x)
            return obj
      """, pythonpath=[d.path])

  def test_init_with_no_params(self):
    self.Check("""
      class Foo(object):
        def __init__():
          pass
      """)

  def test_instantiate_with_abstract_dict(self):
    ty = self.Infer("""
      X = type("", (), dict())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      X = ...  # type: Any
    """)

  def test_not_instantiable(self):
    self.CheckWithErrors("""
      class Foo(object):
        def __new__(cls):
          assert cls is not Foo, "not instantiable"
        def foo(self):
          name_error  # name-error
    """)

  def test_metaclass_on_unknown_class(self):
    self.Check("""
      import six
      class Foo(type):
        pass
      def decorate(cls):
        return __any_object__
      @six.add_metaclass(Foo)
      @decorate
      class Bar(object):
        pass
    """)

  def test_subclass_contains_base(self):
    ty = self.Infer("""
      def get_c():
        class C(object):
          def __init__(self, z):
            self.a = 3
            self.c = z
          def baz(self): pass
        return C
      class DC(get_c()):
        def __init__(self, z):
          super(DC, self).__init__(z)
          self.b = "hello"
        def bar(self, x): pass
      x = DC(1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class DC(object):
          a = ...  # type: int
          b = ...  # type: str
          c = ...  # type: Any
          def __init__(self, z) -> None: ...
          def bar(self, x) -> None: ...
          def baz(self) -> None: ...
      def get_c() -> type: ...
      x = ...  # type: DC
    """)

  def test_subclass_multiple_base_options(self):
    ty = self.Infer("""
      class A(object): pass
      def get_base():
        class B(object): pass
        return B
      Base = A if __random__ else get_base()
      class C(Base): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      def get_base() -> type: ...
      class A(object): pass
      Base = ...  # type: type
      class C(Any): pass
    """)

  def test_subclass_contains_generic_base(self):
    ty = self.Infer("""
      import typing
      def get_base():
        class C(typing.List[str]):
          def get_len(self): return len(self)
        return C
      class DL(get_base()): pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      typing = ...  # type: module
      class DL(List[str]):
          def get_len(self) -> int: ...
      def get_base() -> type: ...
    """)

  def test_subclass_overrides_base_attributes(self):
    ty = self.Infer("""
      def get_base():
        class B(object):
          def __init__(self):
            self.a = 1
            self.b = 2
          def bar(self, x): pass
          def baz(self): pass
        return B
      class C(get_base()):
        def __init__(self):
          super(C, self).__init__()
          self.b = "hello"
          self.c = "world"
        def bar(self, x): pass
    """)
    self.assertTypesMatchPytd(ty, """
      def get_base() -> type: ...
      class C(object):
        a = ...  # type: int
        b = ...  # type: str
        c = ...  # type: str
        def __init__(self) -> None: ...
        def bar(self, x) -> None: ...
        def baz(self) -> None: ...
    """)

  def test_subclass_make_base(self):
    ty = self.Infer("""
      def make_base(x):
        class C(x):
          def __init__(self):
            self.x = 1
        return C
      class BX(make_base(list)): pass
    """)
    self.assertTypesMatchPytd(ty, """
      def make_base(x) -> type: ...
      class BX(list):
        x = ...  # type: int
        def __init__(self) -> None: ...
    """)

  def test_subclass_bases_overlap(self):
    ty = self.Infer("""
      def make_a():
        class A(object):
          def __init__(self):
            self.x = 1
        return A
      def make_b():
        class B(object):
          def __init__(self):
            self.x = "hello"
        return B
      class C(make_a(), make_b()):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      def make_a() -> type: ...
      def make_b() -> type: ...
      class C(object):
        x = ...  # type: int
        def __init__(self) -> None: ...
    """)

  def test_pyi_nested_class(self):
    # Test that pytype can look up a pyi nested class in a py file and reconsume
    # the inferred pyi.
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X:
          class Y: ...
      """)
      ty = self.Infer("""
        import foo
        Y = foo.X.Y
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        foo: module
        Y: Type[foo.X.Y]
      """)
      d.create_file("bar.pyi", pytd_utils.Print(ty))
      ty = self.Infer("""
        import bar
        Y = bar.Y
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        bar: module
        Y: Type[foo.X.Y]
      """)

  def test_pyi_nested_class_alias(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X:
          class Y: ...
          Z = X.Y
      """)
      ty = self.Infer("""
        import foo
        Z = foo.X.Z
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        foo: module
        Z: Type[foo.X.Y]
      """)

  def test_pyi_deeply_nested_class(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class X:
          class Y:
            class Z: ...
      """)
      ty = self.Infer("""
        import foo
        Z = foo.X.Y.Z
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        import foo
        foo: module
        Z: Type[foo.X.Y.Z]
      """)

  def test_late_annotation(self):
    ty = self.Infer("""
      class Foo(object):
        bar = None  # type: 'Bar'
      class Bar(object):
        def __init__(self):
          self.x = 0
      class Baz(Foo):
        def f(self):
          return self.bar.x
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        bar: Bar
      class Bar(object):
        x: int
        def __init__(self) -> None: ...
      class Baz(Foo):
        def f(self) -> int: ...
    """)

  def test_iterate_ambiguous_base_class(self):
    self.Check("""
      from typing import Any
      class Foo(Any):
        pass
      list(Foo())
    """)

  def test_instantiate_class(self):
    self.Check("""
      import abc
      import six
      @six.add_metaclass(abc.ABCMeta)
      class Foo(object):
        def __init__(self, x):
          if x > 0:
            print(self.__class__(x-1))
        @abc.abstractmethod
        def f(self):
          pass
    """)


test_base.main(globals(), __name__ == "__main__")
