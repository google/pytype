"""Tests for disabling errors."""

from pytype.tests import test_inference


class DisableTest(test_inference.InferenceTest):
  """Test error disabling."""

  def testInvalidDirective(self):
    _, errors = self.InferAndCheck("""\
      x = 1  # pytype: this is not a valid pytype directive.
    """)
    self.assertErrorLogIs(errors, [(1, "invalid-directive")])
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def testInvalidDisableErrorName(self):
    _, errors = self.InferAndCheck("""\
      x = 1  # pytype: disable=not-an-error.
    """)
    self.assertErrorLogIs(errors, [(1, "invalid-directive",
                                    r"Invalid error name.*not-an-error")])
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def testDisableError(self):
    _, errors = self.InferAndCheck("""\
      x = a
      x = b  # pytype: disable=name-error
      x = c
    """)
    self.assertErrorLogIs(errors, [(1, "name-error"), (3, "name-error")])

  def testOpenEndedDirective(self):
    """Test that disables in the middle of the file can't be left open-ended."""
    _, errors = self.InferAndCheck("""\
      '''This is a docstring.
      def f(x):
        pass
      class A(object):
        pass
      The above definitions should be ignored.
      '''
      # pytype: disable=attribute-error  # ok (before first class/function def)
      CONSTANT = 42
      # pytype: disable=not-callable  # ok (before first class/function def)
      def f(x):
        # type: ignore  # bad
        pass
      def g(): pass
      x = y  # pytype: disable=name-error  # ok (single line)
      # pytype: disable=none-attr  # ok (re-enabled)
      # pytype: disable=wrong-arg-types  # bad
      # pytype: enable=none-attr
    """)
    self.assertErrorLogIs(errors, [(12, "late-directive", "Type checking"),
                                   (17, "late-directive", "wrong-arg-types")])
    # late-directive is a warning
    self.assertFalse(errors.has_error())


if __name__ == "__main__":
  test_inference.main()
