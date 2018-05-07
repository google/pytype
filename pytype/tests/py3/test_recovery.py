"""Tests for recovering after errors."""

from pytype.tests import test_base


class RecoveryTests(test_base.TargetPython3BasicTest):
  """Tests for recovering after errors."""

  def testFunctionWithUnknownDecorator(self):
    _, errors = self.InferWithErrors("""\
            from nowhere import decorator
      @decorator
      def f():
        name_error
      @decorator
      def g(x: int) -> None:
        x.upper()
    """, deep=True)
    self.assertErrorLogIs(errors, [
        (2, "import-error"),
        (5, "name-error"),
        (8, "attribute-error"),
    ])

  def testComplexInit(self):
    """Test that we recover when __init__ triggers a utils.TooComplexError."""
    _, errors = self.InferWithErrors("""\
            from typing import AnyStr
      class X(object):
        def __init__(self,
                     literal: int = None,
                     target_index: int = None,
                     register_range_first: int = None,
                     register_range_last: int = None,
                     method_ref: AnyStr = None,
                     field_ref: AnyStr = None,
                     string_ref: AnyStr = None,
                     type_ref: AnyStr = None) -> None:
          pass
        def foo(self, x: other_module.X) -> None:  # line 14
          pass
    """, deep=True)
    self.assertErrorLogIs(errors, [(14, "name-error", r"other_module")])


if __name__ == "__main__":
  test_base.main()
