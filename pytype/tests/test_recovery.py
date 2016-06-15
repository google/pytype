"""Tests for recovering after errors."""

from pytype.tests import test_inference


class RecoveryTests(test_inference.InferenceTest):
  """Tests for recovering after errors.

  The type inferencer can warn about bad code, but it should never blow up.
  These tests check that we don't faceplant when we encounter difficult code.
  """

  def testBadSubtract(self):
    ty = self.Infer("""
      def f():
        t = 0.0
        return t - ("bla" - t)
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      def f() -> ?
    """)

  def testBadCall(self):
    ty = self.Infer("""
      def f():
        return "%s" % chr("foo")
    """, deep=True, solve_unknowns=True, report_errors=False)
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
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      time = ...  # type: module
      def f() -> ?
      def g() -> str
    """)

  def testInheritFromInstance(self):
    ty = self.Infer("""
      class Foo(3):
        pass
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(?):
        pass
    """)

  def testNameError(self):
    ty = self.Infer("""
      x = foobar
      class A(x):
        pass
      pow(A(), 2)
    """, deep=True, solve_unknowns=True, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: ?
      class A(?):
        pass
    """)


if __name__ == "__main__":
  test_inference.main()
