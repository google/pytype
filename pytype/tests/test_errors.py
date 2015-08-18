"""Tests for displaying errors."""

from pytype.tests import test_inference


class ErrorTest(test_inference.InferenceTest):
  """Tests for errors."""

  def testInvalidAttribute(self):
    ty, errors = self.InferAndCheck("""
      class A(object):
        pass
      def f():
        (3).parrot
        return "foo"
    """)
    self.assertTypesMatchPytd(ty, """
      class A:
        pass

      def f() -> str
    """)
    self.assertErrorLogContains(errors, "line 5.*attribute.*parrot.*int")


if __name__ == "__main__":
  test_inference.main()
