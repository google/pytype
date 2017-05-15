"""Tests for displaying tracebacks in error messages."""

from pytype.tests import test_inference


class TracebackTest(test_inference.InferenceTest):
  """Tests for tracebacks in error messages."""

  def test_no_traceback(self):
    _, errors = self.InferAndCheck("""\
      def f(x):
        "hello" + 42
      f("world")
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types", r"str.*int\)$")])

  def test_same_traceback(self):
    _, errors = self.InferAndCheck("""\
      def f(x):
        x + 42
      def g(x):
        f("hello")
      g("world")
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types",
                                    r"Traceback:\n  line 4, in g")])

  def test_different_tracebacks(self):
    _, errors = self.InferAndCheck("""\
      def f(x):
        x + 42
      f("hello")
      f("world")
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-types",
                                    r"Traceback:\n  line 3, in <module>"),
                                   (2, "wrong-arg-types",
                                    r"Traceback:\n  line 4, in <module>")])


if __name__ == "__main__":
  test_inference.main()
