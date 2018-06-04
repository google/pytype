"""Tests for pytype_source_utils.py."""

import os

from pytype import pytype_source_utils

import unittest


class PytypeSourceUtilsTest(unittest.TestCase):
  """Test pytype source utilities."""

  def setUp(self):
    self.root = os.path.dirname(__file__)

  def testPytypeSourceDir(self):
    self.assertEqual(self.root, pytype_source_utils.pytype_source_dir())

  def testGetFullPath(self):
    self.assertEqual(
        os.path.join(self.root, "foo/bar"),
        pytype_source_utils.get_full_path("foo/bar"))
    self.assertEqual(
        "/foo/bar",
        pytype_source_utils.get_full_path("/foo/bar"))

  def testListPytypeFiles(self):
    l = list(pytype_source_utils.list_pytype_files("pytd/stdlib/2"))
    self.assertIn("ctypes.pytd", l)
    self.assertIn("collections.pytd", l)


if __name__ == "__main__":
  unittest.main()
