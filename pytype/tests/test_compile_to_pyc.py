# coding=utf-8
"""Tests for compilation to bytecode."""

from pytype.tests import test_base


class CompileToPycTest(test_base.TargetIndependentTest):
  """Tests for compilation to bytecode."""

  def testCompilationOfUnicodeSource(self):
    self.Check("print('←↑→↓')")

  def testCompilationOfUnicodeSourceWithEncoding(self):
    self.Check("# encoding: utf-8\nprint('←↑→↓')")
    self.Check("#! my/python\n# encoding: utf-8\nprint('←↑→↓')")

  def testErrorLineNumbersWithEncoding1(self):
    self.CheckWithErrors("""\
      # coding: utf-8
      def foo():
        return "1".hello  # attribute-error
    """)

  def testErrorLineNumbersWithEncoding2(self):
    self.CheckWithErrors("""\
      #! /bin/python
      # coding: utf-8
      def foo():
        return "1".hello  # attribute-error
    """)

test_base.main(globals(), __name__ == "__main__")
