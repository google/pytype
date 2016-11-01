"""Tests for --check."""

import os
import textwrap

from pytype import config
from pytype import errors
from pytype import infer
from pytype.tests import test_inference


class CheckerTest(test_inference.InferenceTest):
  """Tests for --check."""


  def get_checking_errors(self, python, pytd=None):
    options = config.Options.create(python_version=self.PYTHON_VERSION,
                                    python_exe=self.PYTHON_EXE)
    errorlog = errors.ErrorLog()
    infer.check_types(py_src=textwrap.dedent(python),
                      pytd_src=None if pytd is None else textwrap.dedent(pytd),
                      py_filename="<inline>",
                      pytd_filename="<inline>",
                      errorlog=errorlog,
                      options=options,
                      cache_unknowns=True)
    return errorlog

  def check(self, python, pytd=None):
    errorlog = self.get_checking_errors(python, pytd)
    if errorlog.has_error():
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
    self.check(python, pytd)

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
    self.check(python, pytd)

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
    self.check(python, pytd)

  def testSet(self):
    python = """
      from __future__ import google_type_annotations
      from typing import List, Set
      def f(data: List[str]):
        data = set(x for x in data)
        g(data)
      def g(data: Set[str]):
        pass
    """
    self.check(python)

  def testRecursiveForwardReference(self):
    python = """
      from __future__ import google_type_annotations
      class X(object):
        def __init__(self, val: "X"):
          pass
      X(42)  # No error because we couldn't instantiate the type of val
    """
    errorlog = self.get_checking_errors(python)
    self.assertErrorLogIs(errorlog, [(0, "recursion-error", r"X")])


if __name__ == "__main__":
  test_inference.main()
