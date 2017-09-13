"""Tests of special builtins (special_builtins.py."""


from pytype.tests import test_inference


class SpecialBuiltinsTest(test_inference.InferenceTest):
  """Tests for special_builtins.py."""

  def testNext(self):
    self.assertNoCrash("""
      next(None)
    """)

  def testNext2(self):
    self.assertNoCrash("""
      class Foo(object):
        def a(self):
          self._foo = None
        def b(self):
          self._foo = __any_object__
        def c(self):
          next(self._foo)
    """)

  def testAbs(self):
    self.assertNoCrash("""
      abs(None)
    """)

  def testPropertyMatching(self):
    self.assertNoErrors("""
      class A():
        def setter(self, other):
          pass
        def getter(self):
          return 42
        def create_property(self, cls, property_name):
          setattr(cls, property_name, property(self.getter, self.setter))
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
    """, deep=True)
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
    """, deep=True)
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



if __name__ == "__main__":
  test_inference.main()
