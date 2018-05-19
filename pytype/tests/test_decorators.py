"""Test for function and class decorators."""

from pytype import file_utils
from pytype.tests import test_base


class DecoratorsTest(test_base.TargetIndependentTest):
  """Test for function and class decorators."""

  def testStaticMethodSmoke(self):
    self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          # python-dateutil uses the old way of using @staticmethod:
          list = staticmethod(list)
    """, show_library_calls=True)

  def testStaticMethod(self):
    ty = self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          list = staticmethod(list)
    """, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      class tzwinbase(object):
        @staticmethod
        def list() -> None: ...
    """)

  def testStaticMethodReturnType(self):
    ty = self.Infer("""
      class Foo(object):
        @staticmethod
        def bar():
          return "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        @staticmethod
        def bar() -> str: ...
    """)

  def testBadStaticMethod(self):
    ty = self.Infer("""
      class Foo(object):
        bar = 42
        bar = staticmethod(bar)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        bar = ...  # type: Any
    """)

  def testClassMethod(self):
    ty = self.Infer("""
      class Foo(object):
        @classmethod
        def f(cls):
          return "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        @classmethod
        def f(cls) -> str: ...
    """)

  def testBadClassMethod(self):
    ty = self.Infer("""
      class Foo(object):
        bar = 42
        bar = classmethod(bar)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        bar = ...  # type: Any
    """)

  def testBadKeyword(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __init__(self):
          self._bar = 1
        def _SetBar(self, value):
          self._bar = value
        bar = property(should_fail=_SetBar)
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-keyword-args", r"should_fail")])

  def testFgetIsOptional(self):
    self.Check("""
      class Foo(object):
        def __init__(self):
          self._bar = 1
        def _SetBar(self, value):
          self._bar = value
        bar = property(fset=_SetBar)
        """)

  def testProperty(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, x):
          self.x = x
        @property
        def f(self):
          return self.x
        @f.setter
        def f(self, x):
          self.x = x
        @f.deleter
        def f(self):
          del self.x

      foo = Foo("foo")
      foo.x = 3
      x = foo.x
      del foo.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        f = ...  # type: Any
        x = ...  # type: Any
        def __init__(self, x) -> None
      foo = ...  # type: Foo
      x = ...  # type: int
    """)

  def testPropertyConstructor(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, x):
          self.x = x
        def _get(self):
          return self.x
        def _set(self, x):
          self.x = x
        def _del(self):
          del self.x
        x = property(fget=_get, fset=_set, fdel=_del)
      foo = Foo("foo")
      foo.x = 3
      x = foo.x
      del foo.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        x = ...  # type: Any
        def __init__(self, x) -> None
        def _del(self) -> None: ...
        def _get(self) -> Any: ...
        def _set(self, x) -> None: ...
      foo = ...  # type: Foo
      x = ...  # type: int
    """)

  def testPropertyConstructorPosargs(self):
    # Same as the above test but with posargs for fget, fset, fdel
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, x):
          self.x = x
        def _get(self):
          return self.x
        def _set(self, x):
          self.x = x
        def _del(self):
          del self.x
        x = property(_get, _set, _del)
      foo = Foo("foo")
      foo.x = 3
      x = foo.x
      del foo.x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        x = ...  # type: Any
        def __init__(self, x) -> None
        def _del(self) -> None: ...
        def _get(self) -> Any: ...
        def _set(self, x) -> None: ...
      foo = ...  # type: Foo
      x = ...  # type: int
    """)

  def testPropertyType(self):
    ty = self.Infer("""
      class Foo(object):
        if __random__:
          @property
          def name(self):
            return 42
        else:
          @property
          def name(self):
            return [42]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo(object):
        name = ...  # type: int or List[int]
    """)

  def testOverwritePropertyType(self):
    ty = self.Infer("""
      class Foo(object):
        @property
        def name(self):
          return 42
        @name.getter
        def name(self):
          return "hello"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        name = ...  # type: str
    """)

  def testUnknownPropertyType(self):
    ty = self.Infer("""
      class Foo(object):
        def name(self, x):
          self._x = x
        name = property(fset=name)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        name = ...  # type: Any
    """)

  def testBadFget(self):
    ty = self.Infer("""
      class Foo(object):
        v = "hello"
        name = property(v)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        v = ...  # type: str
        name = ...  # type: Any
    """)

  def testInferCalledDecoratedMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Callable, List, TypeVar
        T = TypeVar("T")
        def decorator(x: Callable[Any, T]) -> Callable[Any, T]: ...
      """)
      ty = self.Infer("""
        import foo
        class A(object):
          @foo.decorator
          def f(self, x=None):
            pass
        A().f(42)
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Callable
        foo = ...  # type: module
        class A(object):
          f = ...  # type: Callable
      """)

  def testUnknownDecorator(self):
    self.Check("""
      class Foo(object):
        @classmethod
        @__any_object__
        def bar(cls):
          pass
      Foo.bar()
    """)

  def testInstanceAsDecorator(self):
    self.Check("""
      class Decorate(object):
        def __call__(self, func):
          return func
      class Foo(object):
        @classmethod
        @Decorate()
        def bar(cls):
          pass
      Foo.bar()
    """)

  def testInstanceAsDecoratorError(self):
    errors = self.CheckWithErrors("""\
      class Decorate(object):
        def __call__(self, func):
          return func
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate
        def bar(cls):
          pass
      Foo.bar()
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-count", r"Decorate.*1.*2")])

  def testUncallableInstanceAsDecorator(self):
    errors = self.CheckWithErrors("""\
      class Decorate(object):
        pass  # forgot to define __call__
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate
        def bar(cls):
          pass
      Foo.bar()
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-count", r"Decorate.*1.*2"),
                                   (8, "not-callable", r"Decorate")])

  def testAmbiguousClassMethod(self):
    self.Check("""\
      class Foo():
        def __init__(self):
          pass
        @classmethod
        def create(cls):
          return cls()
      class Bar():
        def __init__(self, x):
          pass
        @classmethod
        def create(cls):
          return cls(0)
      (Foo if __random__ else Bar).create()
    """)


test_base.main(globals(), __name__ == "__main__")
