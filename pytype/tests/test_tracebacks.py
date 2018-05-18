"""Tests for displaying tracebacks in error messages."""

from pytype.tests import test_base


class TracebackTest(test_base.TargetIndependentTest):
  """Tests for tracebacks in error messages."""

  def test_no_traceback(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        "hello" + 42
      f("world")
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"str.*int\)$")])

  def test_same_traceback(self):
    _, errors = self.InferWithErrors("""\
      def f(x, _):
        x + 42
      def g(x):
        f("hello", x)
      g("world")
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types",
                                    r"Traceback:\n  line 4, in g")])

  def test_different_tracebacks(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        x + 42
      f("hello")
      f("world")
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types",
                                    r"Traceback:\n  line 3, in <module>"),
                                   (2, "wrong-arg-types",
                                    r"Traceback:\n  line 4, in <module>")])

  def test_comprehension(self):
    _, errors = self.InferWithErrors("""\
      def f():
        return {x.upper() for x in range(10)}
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"upper.*int$")])
    error, = errors
    self.assertEqual(error.methodname, "f")

  def test_comprehension_in_traceback(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        return x.upper()
      def g():
        return {f(x) for x in range(10)}
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error",
                                    r"Traceback:\n  line 4, in g$")])


test_base.main(globals(), __name__ == "__main__")
