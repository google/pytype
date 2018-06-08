# coding=utf-8
"""Tests for compilation to bytecode."""

from pytype.tests import test_base


class CompileToPycTest(test_base.TargetIndependentTest):

  def testCompilationOfUnicodeSource(self):
    self.Check("print('←↑→↓')")  # pylint: disable=invalid-encoded-data


test_base.main(globals(), __name__ == "__main__")
