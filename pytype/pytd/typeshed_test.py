"""Tests for typeshed.py."""

import unittest


from pytype.pytd import typeshed
from pytype.pytd.parse import parser_test_base


class TestTypeshed(parser_test_base.ParserTest):
  """Test the code for loading files from typeshed."""

  def test_get_typeshed_file(self):
    data = typeshed.get_typeshed_file("builtins", "errno", (2, 7))
    self.assertIn("errorcode", data)

  def test_parse_type_definition(self):
    ast = typeshed.parse_type_definition("builtins", "_random", (2, 7))
    self.assertIn("_random.Random", [cls.name for cls in ast.classes])


if __name__ == "__main__":
  unittest.main()
