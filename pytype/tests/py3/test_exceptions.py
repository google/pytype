"""Test exceptions."""

from pytype.tests import test_base


class TestExceptionsPy3(test_base.TargetPython3FeatureTest):
  """Exception tests."""

  def test_reraise(self):
    # Test that we don't crash when trying to reraise a nonexistent exception.
    # (Causes a runtime error when actually run in python 3.6)
    self.assertNoCrash(self.Check, """
      raise
    """)

  def test_raise_exception_from(self):
    self.Check("raise ValueError from NameError")

  def test_exception_message(self):
    # This attribute was removed in Python 3.
    errors = self.CheckWithErrors("ValueError().message")
    self.assertErrorLogIs(errors, [(1, "attribute-error")])


if __name__ == "__main__":
  test_base.main()
