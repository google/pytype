"""Tests for typeshed.py."""

import unittest
import os


from pytype.pytd import typeshed
from pytype.pytd.parse import parser_test_base


class TestTypeshed(parser_test_base.ParserTest):
  """Test the code for loading files from typeshed."""

  def test_get_typeshed_file(self):
    filename, data = typeshed.get_typeshed_file("stdlib", "errno", (2, 7))
    self.assertEqual("errno.pyi", os.path.basename(filename))
    self.assertIn("errorcode", data)

  def test_get_typeshed_dir(self):
    filename, data = typeshed.get_typeshed_file("stdlib", "logging", (2, 7))
    self.assertEqual("__init__.pyi", os.path.basename(filename))
    self.assertIn("LogRecord", data)

  def test_parse_type_definition(self):
    ast = typeshed.parse_type_definition("stdlib", "_random", (2, 7))
    self.assertIn("_random.Random", [cls.name for cls in ast.classes])


if __name__ == "__main__":
  unittest.main()
