"""Tests for disabling errors."""

from pytype.tests import test_inference


class DisableTest(test_inference.InferenceTest):
  """Test error disabling."""

  def testInvalidDirective(self):
    _, errors = self.InferAndCheck("""
      x = 1  # pytype: this is not a valid pytype directive.
    """)
    self.assertErrorLogContains(
        errors, r"line 2.*\[invalid-directive\]")
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def testInvalidDisableErrorName(self):
    _, errors = self.InferAndCheck("""
      x = 1  # pytype: disable=not-an-error.
    """)
    self.assertErrorLogContains(
        errors, r"line 2.*Invalid error name.*not-an-error")
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def testDisableError(self):
    _, errors = self.InferAndCheck("""
      x = a
      x = b  # pytype: disable=name-error
      x = c
    """)
    self.assertErrorLogContains(errors, r"line 2.*name-error")
    self.assertErrorLogDoesNotContain(errors, r"line 3.*name-error")
    self.assertErrorLogContains(errors, r"line 4.*name-error")
    # Verify that only the two expected errors are present (just in case
    # there is a typo in the DoesNotContain regex).
    self.assertEquals(2, len(errors))


if __name__ == "__main__":
  test_inference.main()
