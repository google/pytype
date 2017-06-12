"""Tests for classes."""

import unittest

from pytype import utils
from pytype.tests import test_inference


class ClassesTest(test_inference.InferenceTest):
  """Tests for classes."""

  def testClassDecorator(self):
    ty = self.Infer("""
      @__any_object__
      class MyClass(object):
        def method(self, response):
          pass
      def f():
        return MyClass()
    """, deep=True, solve_unknowns=True, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      # "Callable" because it gets called in f()
      MyClass = ...  # type: classmethod or staticmethod or type or Callable
      def f() -> ?
    """)

  def testClassName(self):
    ty = self.Infer("""
      class MyClass(object):
        def __init__(self, name):
          pass
      def f():
        factory = MyClass
        return factory("name")
      f()
    """, deep=False, solve_unknowns=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
    class MyClass(object):
      def __init__(self, name: str) -> NoneType

    def f() -> MyClass
    """)

  def testInheritFromUnknown(self):
    ty = self.Infer("""
      class A(__any_object__):
        pass
    """, deep=False, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
    class A(?):
      pass
    """)

  def testInheritFromUnknownAndCall(self):
    ty = self.Infer("""
      x = __any_object__
      class A(x):
        def __init__(self):
          x.__init__(self)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    x = ...  # type: ?
    class A(?):
      def __init__(self) -> NoneType
    """)

  def testInheritFromUnknownAndSetAttr(self):
    ty = self.Infer("""
      class Foo(__any_object__):
        def __init__(self):
          setattr(self, "test", True)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    class Foo(?):
      def __init__(self) -> NoneType
    """)

  def testInheritFromUnknownAndInitialize(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      class Bar(Foo, __any_object__):
        pass
      x = Bar(duration=0)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        pass
      class Bar(Foo, Any):
        pass
      x = ...  # type: Bar
    """)

  def testInheritFromUnsolvable(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      ty = self.Infer("""
        import a
        class Foo(object):
          pass
        class Bar(Foo, a.A):
          pass
        x = Bar(duration=0)
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        a = ...  # type: module
        class Foo(object):
          pass
        class Bar(Foo, Any):
          pass
        x = ...  # type: Bar
      """)

  def testClassMethod(self):
    ty = self.Infer("""
      module = __any_object__
      class Foo(object):
        @classmethod
        def bar(cls):
          module.bar("", '%Y-%m-%d')
      def f():
        return Foo.bar()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    module = ...  # type: ?
    def f() -> NoneType
    class Foo(object):
      @classmethod
      def bar(cls) -> None: ...
    """)

  def testInheritFromUnknownAttributes(self):
    ty = self.Infer("""
      class Foo(__any_object__):
        def f(self):
          self.x = [1]
          self.y = list(self.x)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    from typing import List
    class Foo(?):
      x = ...  # type: List[int, ...]
      y = ...  # type: List[int, ...]
      def f(self) -> NoneType
    """)

  def testInnerClass(self):
    ty = self.Infer("""
      def f():
        class Foo(object):
          x = 3
        l = Foo()
        return l.x
    """, deep=True, solve_unknowns=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> int
    """)

  def testSuper(self):
    ty = self.Infer("""
      class Base(object):
        def __init__(self, x, y):
          pass
      class Foo(Base):
        def __init__(self, x):
          super(Foo, self).__init__(x, y='foo')
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    class Base(object):
      def __init__(self, x, y) -> NoneType
    class Foo(Base):
      def __init__(self, x) -> NoneType
    """)

  def testSuperError(self):
    _, errors = self.InferAndCheck("""\
      class Base(object):
        def __init__(self, x, y, z):
          pass
      class Foo(Base):
        def __init__(self, x):
          super(Foo, self).__init__()
    """)
    self.assertErrorLogIs(errors, [(6, "missing-parameter", r"x")])

  def testSuperInInit(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.x = 3

      class B(A):
        def __init__(self):
          super(B, self).__init__()

        def get_x(self):
          return self.x
    """, deep=True, solve_unknowns=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
        class A(object):
          x = ...  # type: int

        class B(A):
          # TODO(kramm): optimize this out
          x = ...  # type: int
          def get_x(self) -> int
    """)

  def testSuperDiamond(self):
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
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      class A(object):
          x = ...  # type: int
      class B(A):
          y = ...  # type: int
      class C(A):
          y = ...  # type: str
          z = ...  # type: complex
      class D(B, C):
          def get_x(self) -> int
          def get_y(self) -> int
          def get_z(self) -> complex
    """)

  def testInheritFromList(self):
    ty = self.Infer("""
      class MyList(list):
        def foo(self):
          return getattr(self, '__str__')
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class MyList(list):
        def foo(self) -> ?
    """)

  def testClassAttr(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      OtherFoo = Foo().__class__
      Foo.x = 3
      OtherFoo.x = "bar"
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        x = ...  # type: str
      # TODO(kramm): Should this be an alias?
      class OtherFoo(object):
        x = ...  # type: str
    """)

  def testCallClassAttr(self):
    ty = self.Infer("""
      class Flag(object):
        convert_method = int
        def convert(self, value):
          return self.convert_method(value)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import SupportsInt, Type
      class Flag(object):
        convert_method = ...  # type: Type[int]
        def convert(self, value: int or unicode or SupportsInt) -> int
    """)

  def testBoundMethod(self):
    ty = self.Infer("""
      class Random(object):
          def seed(self):
            pass

      _inst = Random()
      seed = _inst.seed
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
    from typing import Any, Callable
    class Random(object):
       def seed(self) -> None: ...

    _inst = ...  # type: Random
    seed = ...  # type: Callable[[], Any]
    """)

  def testMROWithUnsolvables(self):
    ty = self.Infer("""
      from nowhere import X, Y  # pytype: disable=import-error
      class Foo(Y):
        pass
      class Bar(X, Foo, Y):
        pass
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      X = ...  # type: ?
      Y = ...  # type: ?
      class Foo(?):
        ...
      class Bar(?, Foo, ?):
        ...
    """)

  def testProperty(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self._name = "name"
        def test(self):
          return self.name
        name = property(fget=lambda self: self._name)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        _name = ...  # type: str
        name = ...  # type: Any
        def test(self) -> str: ...
    """)

  def testDescriptorSelf(self):
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
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        _name = ...  # type: str
        def __get__(self, obj, objtype) -> str: ...
      class Bar(object):
        foo = ...  # type: Foo
        def test(self) -> str: ...
    """)

  def testDescriptorInstance(self):
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
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        def __get__(self, obj, objtype) -> Any: ...
      class Bar(object):
        _name = ...  # type: str
        foo = ...  # type: Foo
        def test(self) -> str: ...
    """)

  def testDescriptorClass(self):
    ty = self.Infer("""
      class Foo(object):
        def __get__(self, obj, objtype):
          return objtype._name
      class Bar(object):
        def test(self):
          return self.foo
        _name = "name"
        foo = Foo()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        def __get__(self, obj, objtype) -> Any: ...
      class Bar(object):
        _name = ...  # type: str
        foo = ...  # type: Foo
        def test(self) -> str: ...
    """)

  def testGetAttr(self):
    ty = self.Infer("""
      class Foo(object):
        def __getattr__(self, name):
          return "attr"
      def f():
        return Foo().foo
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __getattr__(self, name) -> str: ...
      def f() -> str: ...
    """)

  def testGetAttrPyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __getattr__(self, name) -> str
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.Foo().foo
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> str
      """)

  def testGetAttribute(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return 42
      x = A().x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        def __getattribute__(self, name) -> int
      x = ...  # type: int
    """)

  def testGetAttributePyi(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __getattribute__(self, name) -> int
      """)
      ty = self.Infer("""
        import a
        x = a.A().x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: int
      """)

  def testInheritFromClassobj(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A():
          pass
      """)
      ty = self.Infer("""
        import a
        class C(a.A):
          pass
        name = C.__name__
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ... # type: module
        class C(a.A):
          pass
        name = ... # type: str
      """)

  def testMetaclassGetAttribute(self):
    with utils.Tempdir() as d:
      d.create_file("enum.pyi", """
        from typing import Any
        class EnumMeta(type):
          def __getattribute__(self, name) -> Any
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
      """, pythonpath=[d.path])
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

  def testReturnClassType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A(object):
          x = ...  # type: int
        class B(object):
          x = ...  # type: str
        def f(x: Type[A]) -> Type[A]
        def g() -> Type[A or B]
        def h() -> Type[int or B]
      """)
      ty = self.Infer("""
        import a
        x1 = a.f(a.A).x
        x2 = a.g().x
        x3 = a.h().x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x1 = ...  # type: int
        x2 = ...  # type: int or str
        x3 = ...  # type: str
      """)

  def testCallClassType(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Type
        class A(object): ...
        class B(object):
          MyA = ...  # type: Type[A]
      """)
      ty = self.Infer("""
        import a
        x = a.B.MyA()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: a.A
      """)

  def testCallAlias(self):
    ty = self.Infer("""
      class A: pass
      B = A
      x = B()
    """)
    # We don't care whether the type of x is inferred as A or B, but we want it
    # to always be the same.
    self.assertTypesMatchPytd(ty, """
      class A: ...
      class B: ...
      x = ...  # type: A
    """)

  def testNew(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(object):
          def __new__(cls, x: int) -> B
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
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        class C(object):
          def __new__(cls) -> str
        x1 = ...  # type: a.B
        x2 = ...  # type: str
        x3 = ...  # type: bool
      """)

  def testNewAndInit(self):
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
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Type, TypeVar, Union
      _TA = TypeVar("_TA", bound=A)
      class A(object):
        x = ...  # type: Any
        y = ...  # type: bool
        def __new__(cls: Type[_TA], a, b) -> _TA
        def __init__(self, a, b: Union[complex, typing.Iterable]) -> None
      class B(object):
        def __new__(cls, x: float or int or complex) -> A
        def __init__(self, x) -> None
      x1 = ...  # type: A
      x2 = ...  # type: str
      x3 = ...  # type: A
      x4 = ...  # type: float
      x5 = ...  # type: bool
    """)

  def testNewAndInitPyi(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        N = TypeVar("N")
        class A(Generic[T]):
          def __new__(cls, x) -> A[nothing]
          def __init__(self, x: N):
            self := A[N]
        class B(object):
          def __new__(cls) -> A[str]
          # __init__ should not be called
          def __init__(self, x, y) -> None
      """)
      ty = self.Infer("""
        import a
        x1 = a.A(0)
        x2 = a.B()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x1 = ...  # type: a.A[int]
        x2 = ...  # type: a.A[str]
      """)

  def testGetType(self):
    ty = self.Infer("""
      class A:
        x = 3
      def f():
        return A() if __any_object__ else ""
      B = type(A())
      C = type(f())
      D = type(int)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A:
        x = ...  # type: int
      def f() -> A or str
      class B:
        x = ...  # type: int
      C = ...  # type: Type[A or str]
      D = ...  # type: Type[type]
    """)

  def testTypeAttribute(self):
    ty = self.Infer("""
      class A:
        x = 3
      B = type(A())
      x = B.x
      mro = B.mro()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class A:
        x = ...  # type: int
      class B:
        x = ...  # type: int
      x = ...  # type: int
      mro = ...  # type: list
    """)

  def testTypeSubclass(self):
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
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        def __init__(self, name, bases, dict) -> None
        def f(self) -> float
      Int = ...  # type: Type[int]
      class X(int, object, metaclass=A):
        a = ...  # type: int
      x = ...  # type: X
      a = ...  # type: int
      v = ...  # type: float
    """)

  def testUnionBaseClass(self):
    self.assertNoErrors("""\
      import typing
      class A(tuple): pass
      class B(tuple): pass
      class Foo(typing.Union[A,B]): pass
      """)

  def testMetaclassPyi(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        class A(type):
          def f(self) -> float
        class X(metaclass=A): ...
      """)
      ty = self.Infer("""
        import a
        v = a.X.f()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        v = ...  # type: float
      """)

  def testUnsolvableMetaclass(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Any
        def __getattr__(name) -> Any
      """)
      d.create_file("b.pyi", """
        from a import A
        class B(metaclass=A): ...
      """)
      ty = self.Infer("""
        import b
        x = b.B.x
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        b = ...  # type: module
        x = ...  # type: Any
      """)

  def testTypeChange(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.__class__ = int
      x = "" % type(A())
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass
      x = ...  # type: str
    """)

  def testMakeType(self):
    ty = self.Infer("""
      X = type("X", (int, object), {"a": 1})
      x = X()
      a = X.a
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class X(int, object):
        a = ...  # type: int
      x = ...  # type: X
      a = ...  # type: int
    """)

  def testMakeSimpleType(self):
    ty = self.Infer("""
      X = type("X", (), {})
      x = X()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class X(object): ...
      x = ...  # type: X
    """)

  def testMakeAmbiguousType(self):
    ty = self.Infer("""
      if __any_object__:
        name = "A"
      else:
        name = "B"
      X = type(name, (int, object), {"a": 1})
      x = X()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      name = ...  # type: str
      X = ...  # type: Any
      x = ...  # type: Any
    """)

  @unittest.skip("A.__init__ needs to be called")
  def testTypeInit(self):
    ty = self.Infer("""
      class A(type):
        def __init__(self, name, bases, members):
          self.x = 42
          super(A, self).__init__(name, bases, members)
      B = A("B", (), {})
      class C(object):
        __metaclass__ = A
      x1 = B.x
      x2 = C.x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        x = ...  # type: int
        def __init__(self, name, bases, members) -> None
      class B(object, metaclass=A): ...
      class C(object, metaclass=A):
        __metaclass__ = ...  # type: Type[A]
      x1 = ...  # type: int
      x2 = ...  # type: int
    """)

  def testSetMetaclass(self):
    ty = self.Infer("""
      class A(type):
        def f(self):
          return 3.14
      class X(object):
        __metaclass__ = A
      v = X.f()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type):
        def f(self) -> float
      class X(object, metaclass=A):
        __metaclass__ = ...  # type: Type[A]
      v = ...  # type: float
    """)

  def testNoMetaclass(self):
    # In both of these cases, the metaclass should not actually be set.
    ty = self.Infer("""
      class A(type): pass
      X1 = type("X1", (), {"__metaclass__": A})
      class X2(object):
        __metaclass__ = type
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class A(type): ...
      class X1(object):
        __metaclass__ = ...  # type: Type[A]
      class X2(object):
        __metaclass__ = ...  # type: Type[type]
    """)

  def testMetaclass(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class MyMeta(type):
          def register(self, cls: type) -> None
        def mymethod(funcobj: T) -> T
      """)
      ty = self.Infer("""
        import foo
        class X(object):
          __metaclass__ = foo.MyMeta
          @foo.mymethod
          def f(self):
            return 42
        X.register(tuple)
        v = X().f()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Type
        foo = ...  # type: module
        class X(object, metaclass=foo.MyMeta):
          __metaclass__ = ...  # type: Type[foo.MyMeta]
          def f(self) -> int
        v = ...  # type: int
      """)

  @unittest.skip("Setting __metaclass__ to a function doesn't work yet.")
  def testFunctionAsMetaclass(self):
    ty = self.Infer("""
      def MyMeta(name, bases, members):
        return type(name, bases, members)
      class X(object):
        __metaclass__ = MyMeta
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def MyMeta(names, bases, members) -> Any
      class X(object, metaclass=MyMeta):
        def __metaclass__(names, bases, members) -> Any
    """)

  def testClassGetItem(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      class A(type):
        def __getitem__(self, i):
          return 42
      X = A("X", (object,), {})
      v = X[0]
    """)
    self.assertTypesMatchPytd(ty, """
      class A(type):
        def __getitem__(self, i: int) -> int
      class X(object, metaclass=A): ...
      v = ...  # type: int
    """)

  def testBadMroParameterizedClass(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class A(Generic[T]): ...
        class B(A[T]): ...
        class C(A[T], B[T]): ...
        def f() -> C[int]: ...
      """)
      _, errors = self.InferAndCheck("""\
        import foo
        foo.f()
      """, pythonpath=[d.path])
      self.assertErrorLogIs(errors, [(2, "mro-error", r"Class C")])

  def testErrorfulConstructors(self):
    ty, errors = self.InferAndCheck("""\
      class Foo(object):
        attr = 42
        def __new__(cls):
          return name_error
        def __init__(self):
          self.attribute_error
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
        def f(self) -> int: ...
    """)
    self.assertErrorLogIs(errors, [(4, "name-error"), (6, "attribute-error")])

  def testNewFalse(self):
    ty = self.Infer("""\
      class Foo(object):
        def __new__(cls):
          return False
        def __init__(self):
          self.instance_attr = ""
        def f(self):
          return self.instance_attr
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        instance_attr = ...  # type: str
        def __new__(cls) -> bool: ...
        def f(self) -> str: ...
    """)

  def testNewAmbiguous(self):
    ty = self.Infer("""
      class Foo(object):
        def __new__(cls):
          if __random__:
            return super(cls).__new__(cls)
          else:
            return "hello world"
        def __init__(self):
          self.instance_attr = ""
        def f(self):
          return self.instance_attr
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        instance_attr = ...  # type: str
        def __new__(cls) -> str or Foo
        def f(self) -> str
    """)

  def testNewExtraArg(self):
    self.assertNoErrors("""
      class Foo(object):
        def __new__(cls, _):
          return super(Foo, cls).__new__(cls)
      Foo("Foo")
    """)

  def testSuperNewExtraArg(self):
    self.assertNoErrors("""
      class Foo(object):
        def __init__(self, x):
          pass
        def __new__(cls, x):
          # The extra arg is okay because __init__ is defined.
          return super(Foo, cls).__new__(cls, x)
    """)

  def testSuperInitExtraArg(self):
    self.assertNoErrors("""
      class Foo(object):
        def __init__(self, x):
          # The extra arg is okay because __new__ is defined.
          super(Foo, self).__init__(x)
        def __new__(cls, x):
          return super(Foo, cls).__new__(cls)
    """)

  def testSuperInitExtraArg2(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def __new__(cls, a, b) -> Foo
      """)
      self.assertNoErrors("""
        import foo
        class Bar(foo.Foo):
          def __init__(self, a, b):
            # The extra args are okay because __new__ is defined on Foo.
            super(Bar, self).__init__(a, b)
      """, pythonpath=[d.path])

  def testSuperNewWrongArgCount(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __new__(cls, x):
          return super(Foo, cls).__new__(cls, x)
    """, deep=True)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-count", "1.*2")])

  def testSuperInitWrongArgCount(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __init__(self, x):
          super(Foo, self).__init__(x)
    """, deep=True)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-count", "1.*2")])

  def testSuperNewMissingParameter(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __new__(cls, x):
          # Even when __init__ is defined, too few args is an error.
          return super(Foo, cls).__new__()
        def __init__(self, x):
          pass
    """, deep=True)
    self.assertErrorLogIs(errors, [(4, "missing-parameter", r"cls.*__new__")])

  def testNewAnnotatedCls(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import Type
      class Foo(object):
        def __new__(cls: Type[str]):
          return super(Foo, cls).__new__(cls)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class Foo(object):
        def __new__(cls: Type[str]) -> str: ...
    """)

  def testNewKwarg(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __new__(cls):
          # ok because __init__ is defined.
          return super(Foo, cls).__new__(cls, x=42)
        def __init__(self):
          pass
      class Bar(object):
        def __new__(cls):
          return super(Bar, cls).__new__(cls, x=42)  # bad!
    """, deep=True)
    self.assertErrorLogIs(errors, [(9, "wrong-keyword-args", r"x.*__new__")])

  def testInitKwarg(self):
    _, errors = self.InferAndCheck("""\
      class Foo(object):
        def __init__(self):
          # ok because __new__ is defined.
          super(Foo, self).__init__(x=42)
        def __new__(cls):
          return super(Foo, cls).__new__(cls)
      class Bar(object):
        def __init__(self):
          super(Bar, self).__init__(x=42)  # bad!
    """, deep=True)
    self.assertErrorLogIs(errors, [(9, "wrong-keyword-args", r"x.*__init__")])

  def testRecursiveConstructor(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import List
      MyType = List['Foo']
      class Foo(object):
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
        def Convert(self):
          self.x
    """)

  def testRecursiveConstructorAttribute(self):
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import List
      MyType = List['Foo']
      class Foo(object):
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
          self.x[0].x
    """)

  def testRecursiveConstructorBadAttribute(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import List
      MyType = List['Foo']
      class Foo(object):
        def __init__(self, x):
          self.Create(x)
        def Create(self, x: MyType):
          self.x = x
        def Convert(self):
          self.y
    """)
    self.assertErrorLogIs(errors, [(10, "attribute-error", r"y.*Foo")])


if __name__ == "__main__":
  test_inference.main()
