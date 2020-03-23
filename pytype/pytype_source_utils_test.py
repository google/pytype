"""Tests for pytype_source_utils.py."""

import os
import sys

from pytype import pytype_source_utils

import unittest


class PytypeSourceUtilsTest(unittest.TestCase):
  """Test pytype source utilities."""

  def setUp(self):
    super(PytypeSourceUtilsTest, self).setUp()
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
    self.assertIn("_ctypes.pytd", l)
    self.assertIn("collections.pytd", l)

  def testGetCustomPythonExe27(self):
    exe = pytype_source_utils.get_custom_python_exe((2, 7))
    self.assertIn("2.7", exe)

  @unittest.skipUnless(sys.version_info.major == 3, "requires Python 3")
  def testGetCustomPythonExe3(self):
    exe = pytype_source_utils.get_custom_python_exe(sys.version_info[:2])
    self.assertIn("python3", exe)


if __name__ == "__main__":
  unittest.main()
