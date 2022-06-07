"""Tests for pytype_source_utils.py."""

import os

from pytype import pytype_source_utils

import unittest


class PytypeSourceUtilsTest(unittest.TestCase):
  """Test pytype source utilities."""

  def setUp(self):
    super().setUp()
    self.root = os.path.dirname(__file__)

  def test_pytype_source_dir(self):
    self.assertEqual(self.root, pytype_source_utils.pytype_source_dir())

  def test_get_full_path(self):
    self.assertEqual(
        os.path.join(self.root, "foo/bar"),
        pytype_source_utils.get_full_path("foo/bar"))
    self.assertEqual(
        "/foo/bar",
        pytype_source_utils.get_full_path("/foo/bar"))

  def test_list_pytype_files(self):
    l = list(pytype_source_utils.list_pytype_files("stubs/stdlib"))
    self.assertIn("_ctypes.pytd", l)
    self.assertIn("collections/__init__.pytd", l)


if __name__ == "__main__":
  unittest.main()
