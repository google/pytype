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
      class Foo(object):
        elements = ...  # type: Any
        def __init__(self, elements: Any) -> None: ...
        def bar(self) -> Any: ...
    """)


if __name__ == "__main__":
  test_inference.main()
