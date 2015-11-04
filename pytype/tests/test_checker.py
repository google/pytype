"""Tests for --check."""

import textwrap

from pytype import errors
from pytype import infer
from pytype.tests import test_inference


class CheckerTest(test_inference.InferenceTest):
  """Tests for --check."""

  def get_checking_errors(self, python, pytd):
    errorlog = errors.ErrorLog()
    infer.check_types(py_src=textwrap.dedent(python),
                      pytd_src=textwrap.dedent(pytd),
                      py_filename="<inline>",
                      pytd_filename="<inline>",
                      python_version=self.PYTHON_VERSION,
                      errorlog=errorlog,
                      cache_unknowns=True)
    return errorlog

  def check_against_pytd(self, python, pytd):
    errorlog = self.get_checking_errors(python, pytd)
    if errorlog:
      errorlog.print_to_stderr()
      self.fail("Inferencer found %d errors" % len(errorlog))

  def testBasic(self):
    pytd = """
      def f() -> int
    """
    python = """
      def f():
        return 3
    """
    self.check_against_pytd(python, pytd)

  def testError(self):
    pytd = """
      def f(x) -> int
    """
    python = """
      def f(x):
        return 3.14
    """
    errorlog = self.get_checking_errors(python, pytd)
    self.assertErrorLogContains(
        errorlog, r"line 3, in f.*return type is float, should be int")

  def testUnion(self):
    pytd = """
      def f(x: int or float) -> int or float
    """
    python = """
      def f(x):
        return x + 1
    """
    self.check_against_pytd(python, pytd)

  def testClass(self):
    pytd = """
      class A(object):
        def method(self, x: int) -> int
    """
    python = """
      class A(object):
        def method(self, x):
          return x
    """
    self.check_against_pytd(python, pytd)


if __name__ == "__main__":
  test_inference.main()
