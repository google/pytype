"""Test for function and class decorators."""

import unittest


from pytype import utils
from pytype.tests import test_inference


class DecoratorsTest(test_inference.InferenceTest):
  """Test for function and class decorators."""

  def testStaticMethodSmoke(self):
    self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          # python-dateutil uses the old way of using @staticmethod:
          list = staticmethod(list)
    """, deep=True, solve_unknowns=False, show_library_calls=True)

  @unittest.skip("TODO(kramm): list appears twice")
  def testStaticMethod(self):
    ty = self.Infer("""
      # from python-dateutil
      class tzwinbase(object):
          def list():
            pass
          list = staticmethod(list)
    """, deep=True, solve_unknowns=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      class tzwinbase(object):
        def list() -> NoneType
    """)

  @unittest.skip("This should fail for some reason it doesn't. Therefore "
                 "testFgetIsOptional is probably a nop test")
  def testFgetIsOptionalFail(self):
    #
    # is probably a nop test.
    self.assertNoErrors("""
      class Foo(object):
        def __init__(self):
          self._bar = 1
        def _SetBar(self, value):
          self._bar = value
        bar = property(should_fail=_SetBar)
        """)

  def testFgetIsOptional(self):
    self.assertNoErrors("""
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        f = ...  # type: property
        x = ...  # type: Any
        def __init__(self, x) -> None
      foo = ...  # type: Foo
      x = ...  # type: int
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
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Callable
        foo = ...  # type: module
        class A(object):
          # "nothing" is present because pytype does not see type parameter
          # values in Callable parameters.
          f = ...  # type: Callable[Any, nothing]
      """)


if __name__ == "__main__":
  test_inference.main()
