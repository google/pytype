"""Tests of special builtins (special_builtins.py)."""

from pytype.tests import test_base


class SpecialBuiltinsTest(test_base.TargetPython3BasicTest):
  """Tests for special_builtins.py."""

  def testPropertyWithTypeParameter(self):
    ty = self.Infer("""
            from typing import Union
      class Foo(object):
        @property
        def foo(self) -> Union[str, int]:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        foo = ...  # type: int or str
    """)

  def testPropertyWithContainedTypeParameter(self):
    ty = self.Infer("""
            from typing import List, Union
      class Foo(object):
        @property
        def foo(self) -> List[Union[str, int]]:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      class Foo(object):
        foo = ...  # type: List[int or str]
    """)

  def testCallableMatching(self):
    self.Check("""
            from typing import Any, Callable
      def f(x: Callable[[Any], bool]):
        pass
      f(callable)
    """)


test_base.main(globals(), __name__ == "__main__")
