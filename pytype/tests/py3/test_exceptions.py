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
    self.CheckWithErrors("ValueError().message  # attribute-error")

  def test_suppress_context(self):
    self.Check("ValueError().__suppress_context__")

  def test_return_or_call_to_raise(self):
    ty = self.Infer("""
      from typing import NoReturn
      def e() -> NoReturn:
        raise ValueError('this is an error')
      def f():
        if __random__:
          return 16
        else:
          e()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn

      def e() -> NoReturn: ...
      def f() -> int: ...
    """)


test_base.main(globals(), __name__ == "__main__")
