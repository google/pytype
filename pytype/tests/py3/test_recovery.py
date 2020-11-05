"""Tests for recovering after errors."""

from pytype.tests import test_base


class RecoveryTests(test_base.TargetPython3BasicTest):
  """Tests for recovering after errors."""

  def test_function_with_unknown_decorator(self):
    self.InferWithErrors("""
      from nowhere import decorator  # import-error
      @decorator
      def f():
        name_error  # name-error
      @decorator
      def g(x: int) -> None:
        x.upper()  # attribute-error
    """, deep=True)

  def test_complex_init(self):
    """Test that we recover when __init__ triggers a utils.TooComplexError."""
    _, errors = self.InferWithErrors("""
      from typing import AnyStr, Optional
      class X(object):
        def __init__(self,
                     literal: Optional[int] = None,
                     target_index: Optional[int] = None,
                     register_range_first: Optional[int] = None,
                     register_range_last: Optional[int] = None,
                     method_ref: Optional[AnyStr] = None,
                     field_ref: Optional[AnyStr] = None,
                     string_ref: Optional[AnyStr] = None,
                     type_ref: Optional[AnyStr] = None) -> None:
          pass
        def foo(self, x: other_module.X) -> None:  # name-error[e]
          pass
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"other_module"})


class RecoveryTestsPython3(test_base.TargetPython3FeatureTest):
  """Tests for recovering after errors(python3 only)."""

  def test_bad_call_parameter(self):
    ty = self.Infer("""
          def f():
            return "%s" % chr("foo")
        """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
          def f() -> str: ...
        """)

  def test_bad_function(self):
    ty = self.Infer("""
        import time
        def f():
          return time.unknown_function(3)
        def g():
          return '%s' % f()
      """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
        from typing import Any
        time = ...  # type: module
        def f() -> Any: ...
        def g() -> str: ...
      """)

test_base.main(globals(), __name__ == "__main__")
