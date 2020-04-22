# coding=utf-8
"""Tests for compilation to bytecode."""

from pytype.tests import test_base


class CompileToPycTest(test_base.TargetIndependentTest):
  """Tests for compilation to bytecode."""

  def test_compilation_of_unicode_source(self):
    self.Check("print('←↑→↓')")

  def test_compilation_of_unicode_source_with_encoding(self):
    self.Check("# encoding: utf-8\nprint('←↑→↓')")
    self.Check("#! my/python\n# encoding: utf-8\nprint('←↑→↓')")

  def test_error_line_numbers_with_encoding1(self):
    self.CheckWithErrors("""
      # coding: utf-8
      def foo():
        return "1".hello  # attribute-error
    """)

  def test_error_line_numbers_with_encoding2(self):
    self.CheckWithErrors("""
      #! /bin/python
      # coding: utf-8
      def foo():
        return "1".hello  # attribute-error
    """)

test_base.main(globals(), __name__ == "__main__")
