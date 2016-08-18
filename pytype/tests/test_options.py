"""Tests for the options you can configure the VM with."""

from pytype.tests import test_inference


class OptionsTest(test_inference.InferenceTest):
  """Tests for VM options."""

  def testNoMaxDepth(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, deep=True, extract_locals=True, maximum_depth=None)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> int
      def f2(x) -> int
      def f3(x) -> int
    """)

  def testMaxDepth0(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, deep=True, extract_locals=True, maximum_depth=0)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> ?
      def f2(x) -> ?
      def f3(x) -> ?
    """)

  def testMaxDepth1(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, deep=True, extract_locals=True, maximum_depth=1)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> ?
      def f2(x) -> ?
      def f3(x) -> int
    """)

  def testMaxDepth2(self):
    ty = self.Infer("""
      def f1(x):
        return f2(x)
      def f2(x):
        return f3(x)
      def f3(x):
        return 1
    """, deep=True, extract_locals=True, maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> ?
      def f2(x) -> ?
      def f3(x) -> int
    """)

  def testInitMaxDepth(self):
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
    """, deep=False, extract_locals=True, init_maximum_depth=2)
    self.assertTypesMatchPytd(ty, """
      def f1(x) -> int
      def f2(x) -> int
      def g1(x) -> ?
      def g2(x) -> ?  # not analyzed
      def g3(x) -> ?  # not analyzed
    """)

if __name__ == "__main__":
  test_inference.main()
