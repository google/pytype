"""Tests for recovering after errors."""

from pytype.tests import test_base


class RecoveryTests(test_base.TargetPython3BasicTest):
  """Tests for recovering after errors."""

  def testFunctionWithUnknownDecorator(self):
    self.InferWithErrors("""
      from nowhere import decorator  # import-error
      @decorator
      def f():
        name_error  # name-error
      @decorator
      def g(x: int) -> None:
        x.upper()  # attribute-error
    """, deep=True)

  def testComplexInit(self):
    """Test that we recover when __init__ triggers a utils.TooComplexError."""
    _, errors = self.InferWithErrors("""
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
        def foo(self, x: other_module.X) -> None:  # name-error[e]
          pass
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"other_module"})


class RecoveryTestsPython3(test_base.TargetPython3FeatureTest):
  """Tests for recovering after errors(python3 only)."""

  def testBadCallParameter(self):
    ty = self.Infer("""
          def f():
            return "%s" % chr("foo")
        """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
          def f() -> str
        """)

  def testBadFunction(self):
    ty = self.Infer("""
        import time
        def f():
          return time.unknown_function(3)
        def g():
          return '%s' % f()
      """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
        time = ...  # type: module
        def f() -> ?
        def g() -> str
      """)

test_base.main(globals(), __name__ == "__main__")
