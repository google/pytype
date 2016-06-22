"""Tests for union types."""

import unittest

from pytype.tests import test_inference


class SplitTest(test_inference.InferenceTest):
  """Tests for union types."""

  def testRestrictNone(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here!
          return y
        else:
          return 123
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> Union[int, str]: ...
    """)

  def testRestrictTrue(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else True

        if y:
          return 123
        else:
          return y
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> Union[int, str]: ...
    """)

  def testRelatedVariable(self):
    ty = self.Infer("""
      def foo(x):
        # y is str or None
        # z is float or True
        if x:
          y = str(x)
          z = 1.23
        else:
          y = None
          z = True

        if y:
          # We only return z when y is true, so z must be a float here.
          return z

        return 123
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> Union[float, int]: ...
    """)

  def testNestedConditions(self):
    ty = self.Infer("""
      def foo(x1, x2):
        y1 = str(x1) if x1 else 0

        if y1:
          if x2:
            return y1  # The y1 condition is still active here.

        return "abc"
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x1, x2) -> str: ...
    """)

  def testRemoveConditionAfterMerge(self):
    ty = self.Infer("""
      def foo(x):
        y = str(x) if x else None

        if y:
          # y can't be None here.
          z = 123
        # But y can be None here.
        return y
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def foo(x) -> Union[None, str]: ...
    """)

  @unittest.skip("If-splitting isn't smart enough for this.")
  def testBroken(self):
    # TODO(dbaum): I don't think this test can work.
    ty = self.Infer("""
      def f2(x):
        if x:
          return x
        else:
          return 3j

      def f1(x):
        y = 1 if x else 0
        if y:
          return f2(y)
        else:
          return None
    """, deep=True, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f2(x) -> Any: ...
      def f1(x) -> Union[complex, int]: ...
    """)


if __name__ == "__main__":
  test_inference.main()
