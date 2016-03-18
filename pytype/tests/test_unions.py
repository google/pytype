"""Tests for union types."""

from pytype.tests import test_inference


class UnionTest(test_inference.InferenceTest):
  """Tests for union types."""

  def testIfElse(self):
    with self.Infer("""
      def id(x):
        return x

      def f(b, x, y):
        return id(1 if b else 1.0)
    """, deep=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def id(x) -> Any

        def f(b, x, y) -> int or float
      """)


if __name__ == "__main__":
  test_inference.main()
