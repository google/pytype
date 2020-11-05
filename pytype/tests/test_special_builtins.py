"""Tests of special builtins (special_builtins.py)."""

from pytype import file_utils
from pytype.tests import test_base


class SpecialBuiltinsTest(test_base.TargetIndependentTest):
  """Tests for special_builtins.py."""

  def test_next(self):
    ty, _ = self.InferWithErrors("""
      a = iter([1, 2, 3])
      b = next(a)
      c = next(42) # wrong-arg-types
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      a: listiterator[int]
      b: int
      c: Any
    """)

  def test_next_none(self):
    self.assertNoCrash(self.Check, """
      next(None)
    """)

  def test_next_ambiguous(self):
    self.assertNoCrash(self.Check, """
      class Foo(object):
        def a(self):
          self._foo = None
        def b(self):
          self._foo = __any_object__
        def c(self):
          next(self._foo)
    """)

  def test_abs(self):
    self.assertNoCrash(self.Check, """
      abs(None)
    """)

  def test_property_matching(self):
    self.Check("""
      class A():
        def setter(self, other):
          pass
        def getter(self):
          return 42
        def create_property(self, cls, property_name):
          setattr(cls, property_name, property(self.getter, self.setter))
    """)

  def test_property_from_pyi(self):
    with file_utils.Tempdir() as d:
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

  def test_property_from_native_function(self):
    ty = self.Infer("""
      class Foo(dict):
        foo = property(fget=dict.__getitem__)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(dict):
        foo = ...  # type: Any
    """)

  def test_property_from_pyi_with_type_parameter(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Union
        class Foo(object):
          def get_foo(self) -> Union[str, int]: ...
      """)
      ty = self.Infer("""
        import foo
        class Bar(foo.Foo):
          foo = property(fget=foo.Foo.get_foo)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Union
        foo = ...  # type: module
        class Bar(foo.Foo):
          foo = ...  # type: Union[str, int]
      """)

  def test_callable_if_splitting(self):
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

  def test_callable(self):
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

  def test_property_change(self):
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
        def __init__(self) -> None: ...
      def f() -> Tuple[int, str]: ...
    """)

  def test_different_property_instances(self):
    errors = self.CheckWithErrors("""
      class Foo(object):
        def __init__(self):
          self._foo = 42 if __random__ else "hello world"
        @property
        def foo(self):
          return self._foo
      foo1 = Foo()
      foo2 = Foo()
      if isinstance(foo1.foo, str):
        x = foo2.foo.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int"})


test_base.main(globals(), __name__ == "__main__")
