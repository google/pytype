"""Tests of special builtins (special_builtins.py)."""

from pytype.tests import test_base


class SpecialBuiltinsTest(test_base.TargetPython3BasicTest):
  """Tests for special_builtins.py."""

  def test_property_with_type_parameter(self):
    ty = self.Infer("""
      from typing import Union
      class Foo(object):
        @property
        def foo(self) -> Union[str, int]:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo(object):
        foo = ...  # type: Union[int, str]
    """)

  def test_property_with_contained_type_parameter(self):
    ty = self.Infer("""
      from typing import List, Union
      class Foo(object):
        @property
        def foo(self) -> List[Union[str, int]]:
          return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      class Foo(object):
        foo = ...  # type: List[Union[int, str]]
    """)

  def test_callable_matching(self):
    self.Check("""
      from typing import Any, Callable
      def f(x: Callable[[Any], bool]):
        pass
      f(callable)
    """)

  def test_filter_starargs(self):
    self.Check("""
      def f(*args, **kwargs):
        filter(*args, **kwargs)
    """)


test_base.main(globals(), __name__ == "__main__")
