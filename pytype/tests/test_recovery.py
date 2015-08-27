"""Tests for recovering after errors."""

from pytype.tests import test_inference


class RecoveryTests(test_inference.InferenceTest):
  """Tests for recovering after errors.

  The type inferencer can warn about bad code, but it should never blow up.
  These tests check that we don't faceplant when we encounter difficult code.
  """

  def testBadSubtract(self):
    with self.Infer("""
      def f():
        t = 0.0
        return t - ("bla" - t)
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> ?
      """)

  def testBadCall(self):
    with self.Infer("""
      def f():
        return "%s" % chr("foo")
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> ?
      """)

  def testBadFunction(self):
    with self.Infer("""
      import time
      def f():
        return time.unknown_function(3)
      def g():
        return '%s' % f()
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        time: module
        def f() -> ?
        def g() -> ?
      """)

  def testInheritFromInstance(self):
    with self.Infer("""
      class Foo(3):
        pass
    """, deep=True, solve_unknowns=True, report_errors=False) as ty:
      self.assertTypesMatchPytd(ty, """
        class Foo(?):
          pass
      """)


if __name__ == "__main__":
  test_inference.main()
