"""Tests for disabling errors."""

from pytype.tests import test_base


class DisableTest(test_base.TargetIndependentTest):
  """Test error disabling."""

  def test_invalid_directive(self):
    _, errors = self.InferWithErrors("""
      x = 1  # pytype: this is not a valid pytype directive.  # invalid-directive
    """)
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def test_invalid_disable_error_name(self):
    _, errors = self.InferWithErrors("""
      x = 1  # pytype: disable=not-an-error.  # invalid-directive[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Invalid error name.*not-an-error"})
    # Invalid directives are just a warning, so has_error() should still
    # return False.
    self.assertFalse(errors.has_error())

  def test_disable_error(self):
    self.InferWithErrors("""
      x = a  # name-error
      x = b  # pytype: disable=name-error
      x = c  # name-error
    """)

  def test_open_ended_directive(self):
    """Test that disables in the middle of the file can't be left open-ended."""
    _, errors = self.InferWithErrors("""
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
        # type: ignore  # late-directive[e1]
        pass
      def g(): pass
      x = y  # pytype: disable=name-error  # ok (single line)
      # pytype: disable=attribute-error  # ok (re-enabled)
      # pytype: disable=wrong-arg-types  # late-directive[e2]
      # pytype: enable=attribute-error
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Type checking", "e2": r"wrong-arg-types"})
    # late-directive is a warning
    self.assertFalse(errors.has_error())

  def test_skip_file(self):
    self.Check("""
      # pytype: skip-file
      name_error
    """)


test_base.main(globals(), __name__ == "__main__")
