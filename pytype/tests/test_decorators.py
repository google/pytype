"""Test for function and class decorators."""


from pytype import utils
from pytype.tests import test_base


class DecoratorsTest(test_base.BaseTest):
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
            return "Foo"
        else:
          @property
          def name(self):
            return u"Bar"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        name = ...  # type: str or unicode
    """)

  def testOverwritePropertyType(self):
    ty = self.Infer("""
      class Foo(object):
        @property
        def name(self):
          return "Foo"
        @name.getter
        def name(self):
          return u"Bar"
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        name = ...  # type: unicode
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
    with utils.Tempdir() as d:
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

  def testAnnotatedSuperCallUnderBadDecorator(self):
    _, errors = self.InferWithErrors("""\
      from __future__ import google_type_annotations
      class Foo(object):
        def Run(self) -> None: ...
      class Bar(Foo):
        @bad_decorator  # line 5
        def Run(self):
          return super(Bar, self).Run()
    """)
    self.assertErrorLogIs(errors, [(5, "name-error", r"bad_decorator")])

  def testAttributeErrorUnderClassDecorator(self):
    _, errors = self.InferWithErrors("""\
      def decorate(cls):
        return __any_object__
      @decorate
      class Foo(object):
        def Hello(self):
          return self.Goodbye()  # line 6
    """)
    self.assertErrorLogIs(errors, [(6, "attribute-error", r"Goodbye")])


if __name__ == "__main__":
  test_base.main()
