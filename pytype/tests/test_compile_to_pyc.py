# coding=utf-8
"""Tests for compilation to bytecode."""

from pytype.tests import test_base


class CompileToPycTest(test_base.TargetIndependentTest):

  def testCompilationOfUnicodeSource(self):
    self.Check("print('←↑→↓')")

  def testCompilationOfUnicodeSourceWithEncoding(self):
    self.Check("# encoding: utf-8\nprint('←↑→↓')")
    self.Check("#! my/python\n# encoding: utf-8\nprint('←↑→↓')")


test_base.main(globals(), __name__ == "__main__")
