"""Tests of special builtins (special_builtins.py."""


from pytype import utils
from pytype.tests import test_base


class SpecialBuiltinsTest(test_base.BaseTest):
  """Tests for special_builtins.py."""

  def testNext(self):
    self.assertNoCrash(self.Check, """
      next(None)
    """)

  def testNext2(self):
    self.assertNoCrash(self.Check, """
      class Foo(object):
        def a(self):
          self._foo = None
        def b(self):
          self._foo = __any_object__
        def c(self):
          next(self._foo)
    """)

  def testAbs(self):
    self.assertNoCrash(self.Check, """
      abs(None)
    """)

  def testPropertyMatching(self):
    self.Check("""
      class A():
        def setter(self, other):
          pass
        def getter(self):
          return 42
        def create_property(self, cls, property_name):
          setattr(cls, property_name, property(self.getter, self.setter))
    """)

  def testPropertyFromPyi(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Foo(object):
          def get_foo(self) -> int: ...
      """)
      ty = self.Infer("""
        import foo
        class Bar(foo.Foo):
          foo = property(fget=foo.Foo.get_foo)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        class Bar(foo.Foo):
          foo = ...  # type: int
      """)

  def testPropertyFromNativeFunction(self):
    ty = self.Infer("""
      class Foo(dict):
        foo = property(fget=dict.__getitem__)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(dict):
        foo = ...  # type: Any
    """)

  def testPropertyWithTypeParameter(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import AnyStr
      class Foo(object):
        @property
        def foo(self) -> AnyStr:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        foo = ...  # type: str or unicode
    """)

  def testPropertyWithContainedTypeParameter(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import AnyStr, List
      class Foo(object):
        @property
        def foo(self) -> List[AnyStr]:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo(object):
        foo = ...  # type: List[str or unicode]
    """)

  def testPropertyFromPyiWithTypeParameter(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import AnyStr
        class Foo(object):
          def get_foo(self) -> AnyStr: ...
      """)
      ty = self.Infer("""
        import foo
        class Bar(foo.Foo):
          foo = property(fget=foo.Foo.get_foo)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        class Bar(foo.Foo):
          foo = ...  # type: str or unicode
      """)

  def testCallableIfSplitting(self):
    ty = self.Infer("""
      def foo(x):
        if callable(x):
          return x(42)
        else:
          return False
      f = lambda x: 10
      a = foo(f)
      b = foo(10)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      a = ...  # type: int
      b = ...  # type: bool
      def f(x) -> int: ...
      def foo(x) -> Any: ...
    """)

  def testCallable(self):
    ty = self.Infer("""
      class A():
        def __call__(self):
          pass
        def foo(self):
          pass
        @staticmethod
        def bar(self):
          pass
        @classmethod
        def baz():
          pass
        @property
        def quux(self):
          pass
      class B():
        pass
      def fun(x):
        pass
      obj = A()
      # All these should be defined.
      if callable(fun): a = 1
      if callable(A): b = 1
      if callable(obj): c = 1
      if callable(obj.foo): d = 1
      if callable(A.bar): e = 1
      if callable(A.baz): f = 1
      if callable(max): g = 1
      if callable({}.setdefault): h = 1
      if callable(hasattr): i = 1
      if callable(callable): j = 1
      # All these should not be defined.
      if callable(obj.quux): w = 1
      if callable(1): x = 1
      if callable([]): y = 1
      if callable(B()): z = 1
    """)
    self.assertTypesMatchPytd(ty, """
      obj = ...  # type: A
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: int
      d = ...  # type: int
      e = ...  # type: int
      f = ...  # type: int
      g = ...  # type: int
      h = ...  # type: int
      i = ...  # type: int
      j = ...  # type: int
      def fun(x) -> None: ...
      class A:
          quux = ...  # type: None
          def __call__(self) -> None: ...
          @staticmethod
          def bar(self) -> None: ...
          @classmethod
          def baz() -> None: ...
          def foo(self) -> None: ...
      class B:
          pass
    """)

  def testCallableMatching(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Any, Callable
      def f(x: Callable[[Any], bool]):
        pass
      f(callable)
    """)

  def testPropertyChange(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.foo = 42
        @property
        def bar(self):
          return self.foo
      def f():
        foo = Foo()
        x = foo.bar
        foo.foo = "hello world"
        y = foo.bar
        return (x, y)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Tuple, Union
      class Foo(object):
        foo = ...  # type: Union[int, str]
        bar = ...  # type: Any
      def f() -> Tuple[int, str]
    """)

  def testDifferentPropertyInstances(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def __init__(self):
          self._foo = 42 if __random__ else "hello world"
        @property
        def foo(self):
          return self._foo
      foo1 = Foo()
      foo2 = Foo()
      if isinstance(foo1.foo, str):
        x = foo2.foo.upper()  # line 10
    """)
    self.assertErrorLogIs(errors, [(10, "attribute-error", r"upper.*int")])


if __name__ == "__main__":
  test_base.main()
