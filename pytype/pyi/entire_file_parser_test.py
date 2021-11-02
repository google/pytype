"""Entire-file parsing test."""

from pytype.pyi import parser_test_base
from pytype.pytd import pytd_utils

import unittest


class EntireFileTest(parser_test_base.ParserTestBase):

  def test_builtins(self):
    _, builtins = pytd_utils.GetPredefinedFile("builtins", "builtins")
    self.check(builtins, expected=parser_test_base.IGNORE)


if __name__ == "__main__":
  unittest.main()
