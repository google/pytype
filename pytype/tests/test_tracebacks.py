"""Tests for displaying tracebacks in error messages."""

from pytype.tests import test_base


class TracebackTest(test_base.TargetIndependentTest):
  """Tests for tracebacks in error messages."""

  def test_no_traceback(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        "hello" + 42  # unsupported-operands[e]
      f("world")
    """)
    self.assertErrorRegexes(errors, {"e": r"expects str$"})

  def test_same_traceback(self):
    _, errors = self.InferWithErrors("""
      def f(x, _):
        x + 42  # unsupported-operands[e]
      def g(x):
        f("hello", x)
      g("world")
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"Called from.*:\n  line 4, in g"})

  def test_different_tracebacks(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        x + 42  # unsupported-operands[e1]  # unsupported-operands[e2]
      f("hello")
      f("world")
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"Called from.*:\n  line 3, in current file",
        "e2": r"Called from.*:\n  line 4, in current file"})

  def test_comprehension(self):
    _, errors = self.InferWithErrors("""
      def f():
        return {x.upper() for x in range(10)}  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int$"})
    error, = errors
    self.assertEqual(error.methodname, "f")

  def test_comprehension_in_traceback(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        return x.upper()  # attribute-error[e]
      def g():
        return {f(x) for x in range(10)}
    """)
    self.assertErrorRegexes(errors, {"e": r"Called from.*:\n  line 4, in g$"})

  def test_no_argument_function(self):
    errors = self.CheckWithErrors("""
      def f():
        return None.attr  # attribute-error[e]
      f()
    """)
    self.assertErrorRegexes(errors, {"e": r"attr.*None$"})

  def test_max_callsites(self):
    errors = self.CheckWithErrors("""
      def f(s):
        return "hello, " + s  # unsupported-operands[e1]  # unsupported-operands[e2]  # unsupported-operands[e3]
      f(0)
      f(1)
      f(2)
      f(3)
    """)
    # We limit the number of tracebacks shown for the same error.
    self.assertErrorRegexes(
        errors, {"e1": r"line 3", "e2": r"line 4", "e3": r"line 5"})


test_base.main(globals(), __name__ == "__main__")
