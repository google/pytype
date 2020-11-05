"""Tests for the options you can configure the VM with."""

from pytype.tests import test_base


class OptionsTest(test_base.TargetIndependentTest):
  """Tests for VM options."""

  def test_no_max_depth(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, maximum_depth=None)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> int: ...
      def f2(x) -> int: ...
      def f3(x) -> int: ...
    """)

  def test_max_depth0(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, maximum_depth=0)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f1(x) -> Any: ...
      def f2(x) -> Any: ...
      def f3(x) -> Any: ...
    """)

  def test_max_depth1(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f1(x) -> Any: ...
      def f2(x) -> Any: ...
      def f3(x) -> int: ...
    """)

  def test_max_depth2(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f1(x) -> Any: ...
      def f2(x) -> int: ...
      def f3(x) -> int: ...
    """)

  def test_init_max_depth(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return 1
      def g1(x):
        return g2(x)
      def g2(x):
        return g3(x)
      def g3(x):
        return 1
      f1(__any_object__)
      g1(__any_object__)
    """, deep=False, init_maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f1(x) -> int: ...
      def f2(x) -> int: ...
      def g1(x) -> Any: ...
      def g2(x) -> Any: ...  # not analyzed
      def g3(x) -> Any: ...  # not analyzed
    """)

  def test_max_depth_for_init(self):
    # This test will fail if we don't whitelist "__init__" methods from
    # maxdepth, because that would prevent the constructor of Foo from being
    # executed.
    _ = self.Infer("""
      class Foo(object):
        def __init__(self):
          self.bar = 0.0
        def get_bar(self):
          return self.bar

      def f1(my_set):
        my_set.add(Foo())
      def f2(my_set):
        f1(my_set)
      def f3(my_set):
        f2(my_set)
      def f4(my_set):
        f3(my_set)

      my_set = set()
      f4(my_set)
      for foo in my_set:
        foo.get_bar()
    """, deep=False, maximum_depth=3, init_maximum_depth=4)


test_base.main(globals(), __name__ == "__main__")
