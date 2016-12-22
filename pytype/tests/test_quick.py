"""Tests for --quick."""

from pytype.tests import test_inference


class QuickTest(test_inference.InferenceTest):
  """Tests for --quick."""

  def testMaxDepth(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, elements):
          assert all(e for e in elements)
          self.elements = elements

        def bar(self):
          return self.elements
    """, deep=True, extract_locals=True, quick=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        elements = ...  # type: Any
        def __init__(self, elements: Any) -> None: ...
        def bar(self) -> Any: ...
    """)

  def testClosure(self):
    ty = self.Infer("""
      def f():
        class A(object): pass
        return {A: A()}
    """, deep=True, extract_locals=True, quick=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f() -> dict
    """)

  def testInit(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          self.real_init()
        def real_init(self):
          self.x = 42
        def f(self):
          return self.x
      def f():
        return A().f()
    """, deep=True, extract_locals=True, quick=True, maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
        x = ...  # type: int
        def real_init(self) -> None
        def f(self) -> Any
      def f() -> Any
    """)


if __name__ == "__main__":
  test_inference.main()
