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
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"expects str$")])

  def test_same_traceback(self):
    _, errors = self.InferWithErrors("""\
      def f(x, _):
        x + 42
      def g(x):
        f("hello", x)
      g("world")
    """, deep=True)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"Called from.*:\n"
                                    r"  line 4, in g")])

  def test_different_tracebacks(self):
    _, errors = self.InferWithErrors("""\
      def f(x):
        x + 42
      f("hello")
      f("world")
    """)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"Called from.*:\n"
                                    r"  line 3, in current file"),
                                   (2, "unsupported-operands",
                                    r"Called from.*:\n"
                                    r"  line 4, in current file")])

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
                                    r"Called from.*:\n  line 4, in g$")])

  def test_no_argument_function(self):
    errors = self.CheckWithErrors("""\
      def f():
        return None.attr
      f()
    """)
    self.assertErrorLogIs(errors, [(2, "attribute-error", r"attr.*None$")])

  def test_build_class(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def f(self, x: Bar):
          pass
    """)
    self.assertErrorLogIs(errors, [(2, "name-error", r"Bar.*not defined$")])


test_base.main(globals(), __name__ == "__main__")
