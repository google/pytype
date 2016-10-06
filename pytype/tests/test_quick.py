"""Tests for --quick."""

from pytype import utils
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
      class Foo(object):
        elements = ...  # type: Any
        def __init__(self, elements: Any) -> None: ...
        def bar(self) -> Any: ...
    """)

  def testAbortOnComplex(self):
    self.assertRaises(utils.ProgramTooComplexError, self.Infer, """
      if __any_object__:
        x = [1]
      else:
        x = [1j]
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
      x = x + x
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


if __name__ == "__main__":
  test_inference.main()
