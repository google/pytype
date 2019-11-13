"""Tests for classes."""

from pytype import file_utils
from pytype.tests import test_base


class ClassesTest(test_base.TargetPython3BasicTest):
  """Tests for classes."""

  def testClassGetItem(self):
    ty = self.Infer("""
      class A(type):
        def __getitem__(self, i):
          return 42
      X = A("X", (object,), {})
      v = X[0]
    """)
    self.assertTypesMatchPytd(ty, """
      class A(type):
        def __getitem__(self, i) -> int
      class X(object, metaclass=A): ...
      v = ...  # type: int
    """)

  def testNewAnnotatedCls(self):
    ty = self.Infer("""
      from typing import Type
      class Foo(object):
        def __new__(cls: Type[str]):
          return super(Foo, cls).__new__(cls)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Type
      class Foo(object):
        def __new__(cls: Type[str]) -> str: ...
    """)

  def testRecursiveConstructor(self):
    self.Check("""
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
    self.Check("""
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
    _, errors = self.InferWithErrors("""\
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
    self.assertErrorLogIs(errors, [(9, "attribute-error", r"y.*Foo")])

  def testRecursiveConstructorSubclass(self):
    self.Check("""
      from typing import List
      MyType = List['Foo']
      class Foo(object):
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

  def testNameExists(self):
    self.Check("""
      class Foo(object): pass
      class Bar(object):
        @staticmethod
        def Create(x: Foo=None):
          return Bar(x)
        @staticmethod
        def bar():
          for name in __any_object__:
            Bar.Create()
            name
        def __init__(self, x: Foo): pass
    """)

  def testInheritFromGenericClass(self):
    ty = self.Infer("""
      from typing import List
      class Foo(List[str]): ...
      v = Foo()[0]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo(List[str]): ...
      v = ...  # type: str
    """)

  def testMakeGenericClass(self):
    ty = self.Infer("""\
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

  def testMakeGenericClassWithConcreteValue(self):
    ty = self.Infer("""\
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

  def testGenericReinstantiated(self):
    """Makes sure the result of foo.f() isn't used by both a() and b()."""
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", "def f() -> list: ...")
      self.Check("""\
        import foo
        from typing import List
        def a() -> List[str]:
          x = foo.f()
          x.append("hello")
          return x
        def b() -> List[int]:
          return [x for x in foo.f()]
        """, pythonpath=[d.path])

  def testParentInit(self):
    errors = self.CheckWithErrors("""\
      from typing import Sequence
      class X(object):
        def __init__(self, obj: Sequence):
          pass
      class Y(X):
        def __init__(self, obj: int):
          X.__init__(self, obj)  # line 7
    """)
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", r"Sequence.*int")])

  def testParameterizedClassBinaryOperator(self):
    _, errors = self.InferWithErrors("""\
      from typing import Sequence
      def f(x: Sequence[str], y: Sequence[str]) -> None:
        a = x + y
      """)
    self.assertErrorLogIs(errors, [(3, "unsupported-operands")])

  def testInstanceAttribute(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self) -> None:
          self.bar = 42
    """, analyze_annotated=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        bar: int
    """)

  def testGenericSuper(self):
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


class ClassesTestPython3Feature(test_base.TargetPython3FeatureTest):
  """Tests for classes."""

  def testClassKwargs(self):
    ty = self.Infer("""
      # x, y are passed to type() or the metaclass. We currently ignore them.
      class Thing(x=True, y="foo"): pass
    """)
    self.assertTypesMatchPytd(ty, """
    class Thing: ...
    """)

  def testMetaclassKwarg(self):
    self.Check("""
      import abc
      class Example(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def foo(self) -> int:
          return None
    """)

  def testBuildClassQuick(self):
    # A() hits maximum stack depth in python3.6
    ty = self.Infer("""\
      def f():
        class A(object): pass
        return {A: A()}
    """, quick=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict: ...
    """)

  def testTypeChange(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.__class__ = int
      x = "" % type(A())
    """)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass
      x = ...  # type: str
    """)

  def testAmbiguousBaseClass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        class Foo(Any): ...
      """)
      # This method will check cleanly once we fix the matcher.py TODO to
      # support matching Any against a parameterized class.
      self.assertNoCrash(self.Check, """
        from typing import Tuple
        import foo
        def f() -> Tuple[int]:
          return foo.Foo()
      """, pythonpath=[d.path])

  def testCallableInheritance(self):
    self.Check("""
      from typing import Callable
      Foo = Callable[[], None]
      class Bar(Foo):
        pass
      def f(x: Foo):
        pass
      f(Bar())
    """)

  def testInitTestClassInSetup(self):
    ty = self.Infer("""\
      import unittest
      class A(unittest.TestCase):
        def setUp(self):
          self.x = 10
        def fooTest(self):
          return self.x
    """)
    self.assertTypesMatchPytd(ty, """
      import unittest
      unittest = ...  # type: module
      class A(unittest.case.TestCase):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)

  def testInitInheritedTestClassInSetup(self):
    ty = self.Infer("""\
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
      unittest = ...  # type: module
      class A(unittest.case.TestCase):
          x = ...  # type: int
      class B(A):
          x = ...  # type: int
          def fooTest(self) -> int: ...
    """)

  def testInitTestClassInInitAndSetup(self):
    ty = self.Infer("""\
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
      unittest = ...  # type: module
      class A(unittest.case.TestCase):
          x = ...  # type: int
          foo = ...  # type: str
          def __init__(self, foo: str) -> NoneType
          def fooTest(self) -> int: ...
    """)

  def testSetMetaclass(self):
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
        def f(self) -> float
      class X(metaclass=A):
        pass
      v = ...  # type: float
    """)

  def testNoMetaclass(self):
    # In this case, the metaclass should not actually be set.
    ty = self.Infer("""
      class X(metaclass=type):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      class X:
        pass
    """)

  def testMetaclass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        T = TypeVar("T")
        class MyMeta(type):
          def register(self, cls: type) -> None
        def mymethod(funcobj: T) -> T
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
        from typing import Type
        foo = ...  # type: module
        class X(metaclass=foo.MyMeta):
          def f(self) -> int
        v = ...  # type: int
      """)

  @test_base.skip("Setting metaclass to a function doesn't work yet.")
  def testFunctionAsMetaclass(self):
    ty = self.Infer("""
      def MyMeta(name, bases, members):
        return type(name, bases, members)
      class X(metaclass=MyMeta):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def MyMeta(names, bases, members) -> Any
      class X(metaclass=MyMeta):
        pass
    """)

  def testUnknownMetaclass(self):
    self.Check("""
      class Foo(metaclass=__any_object__):
        def foo(self):
          self.bar()
        @classmethod
        def bar(cls):
          pass
    """)

  def testPy2Metaclass(self):
    errors = self.CheckWithErrors("""\
      import abc
      class Foo(object):
        __metaclass__ = abc.ABCMeta
        @abc.abstractmethod
        def f(self) -> int: ...
    """)
    self.assertErrorLogIs(
        errors, [(2, "ignored-metaclass", r"abc\.ABCMeta.*Foo")])


test_base.main(globals(), __name__ == "__main__")
