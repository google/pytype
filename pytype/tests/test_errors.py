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

  def testIndexError(self):
    _, errors = self.InferAndCheck("""
      def f():
        return [][0]
    """)
    # "Line 3, in f: Can't retrieve item out of list. Empty?"
    self.assertErrorLogContains(errors, r"line 3.*item out of list")

  def testInvalidBaseClass(self):
    _, errors = self.InferAndCheck("""
      class Foo(3):
        pass
    """)
    # "Line 2, in <module>: Invalid base class: `~unknown0`"
    self.assertErrorLogContains(errors, r"Invalid base class")

if __name__ == "__main__":
  test_inference.main()
