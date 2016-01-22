import unittest
from pytype.pytd import pep484
from pytype.pytd import pytd
from pytype.pytd.parse import parser_test


class TestPEP484(parser_test.ParserTest):
  """Test the visitors in optimize.py."""

  DEFAULT_PYTHON_VERSION = (2, 7)

  def convert(self, t, python_version=None):
    """Run ConvertTypingToNative and return the result as a string."""
    return pytd.Print(t.Visit(
        pep484.ConvertTypingToNative(
            python_version or self.DEFAULT_PYTHON_VERSION)))

  def test_convert_optional(self):
    t = pytd.GenericType(pytd.ExternalType("Optional", module="typing"),
                         (pytd.NamedType("str")))
    self.assertEquals(self.convert(t), "Union[str, None]")

  def test_convert_union(self):
    t = pytd.GenericType(pytd.ExternalType("Union", module="typing"),
                         (pytd.NamedType("str"), pytd.NamedType("float")))
    self.assertEquals(self.convert(t), "Union[str, float]")

  def test_convert_list(self):
    t = pytd.ExternalType("List", module="typing")
    self.assertEquals(self.convert(t), "list")

  def test_convert_tuple(self):
    t = pytd.ExternalType("Tuple", module="typing")
    self.assertEquals(self.convert(t), "tuple")

  def test_convert_any(self):
    t = pytd.ExternalType("Any", module="typing")
    self.assertEquals(self.convert(t), "Any")

  def test_convert_anystr(self):
    t = pytd.ExternalType("AnyStr", module="typing")
    self.assertEquals(self.convert(t, python_version=(2, 7)),
                      "Union[str, unicode]")
    t = pytd.ExternalType("AnyStr", module="typing")
    self.assertEquals(self.convert(t, python_version=(3, 4)),
                      "Union[bytes, str]")


if __name__ == "__main__":
  unittest.main()
