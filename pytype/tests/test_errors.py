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
    self.assertErrorLogContains(errors, r"line 5.*attribute.*parrot.*int")

  def testImportError(self):
    _, errors = self.InferAndCheck("""
      import rumplestiltskin
    """)
    self.assertErrorLogContains(errors, r"line 2.*module.*rumplestiltskin")

  def testWrongArgCount(self):
    _, errors = self.InferAndCheck("""
      hex(1, 2, 3, 4)
    """)
    self.assertErrorLogContains(
        errors, r"line 2.*hex was called with 4 args instead of expected 1")

  def testWrongArgTypes(self):
    _, errors = self.InferAndCheck("""
      hex(3j)
    """)
    self.assertErrorLogContains(
        errors, (r"line 2.*hex was called with the wrong arguments.*"
                 r"expected:.*int.*passed:.*complex"))

if __name__ == "__main__":
  test_inference.main()
