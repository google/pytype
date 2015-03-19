"""Tests for pyc.py."""


from pytype.pyc import pyc
import unittest


class TestPyc(unittest.TestCase):
  """Tests for pyc.py."""

  python_version = (2, 7)

  def test_compile(self):
    pyc_data = pyc.compile_src_string_to_pyc_string(
        "foobar = 3", python_version=self.python_version)
    code = pyc.parse_pyc_string(pyc_data)
    self.assertIn("foobar", code.co_names)
    self.assertEquals(self.python_version, code.python_version)

if __name__ == "__main__":
  unittest.main()
