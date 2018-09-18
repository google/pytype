"""Tests for compat.py."""

import os

from pytype import compat
from pytype import file_utils

import unittest


class RecursiveGlobTest(unittest.TestCase):
  """Test recursive_glob()."""

  def assertPathsEqual(self, paths1, paths2):
    self.assertEqual({os.path.realpath(p) for p in paths1},
                     {os.path.realpath(p) for p in paths2})

  def test_no_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(compat.recursive_glob("foo.py"), ["foo.py"])

  def test_simple_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(compat.recursive_glob("*.py"), ["foo.py"])

  def test_recursive_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py")
      d.create_file("bar/baz.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(compat.recursive_glob("**/*.py"),
                              ["foo.py", "bar/baz.py"])

  def test_redundant_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.py")
      d.create_file("bar/baz.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(compat.recursive_glob("**/**/*.py"),
                              ["foo.py", "bar/baz.py"])

  def test_nested_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo/bar.py")
      d.create_file("foo/baz/qux.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(compat.recursive_glob("foo/**/*.py"),
                              ["foo/bar.py", "foo/baz/qux.py"])

  def test_multiple_magic(self):
    with file_utils.Tempdir() as d:
      d.create_file("d1/d2/d3/f1.py")
      d.create_file("d1/d2/f2.py")
      d.create_file("d2/f3.py")
      d.create_file("d2/d3/f4.py")
      with file_utils.cd(d.path):
        self.assertPathsEqual(
            compat.recursive_glob("**/d2/**/*.py"),
            ["d1/d2/d3/f1.py", "d1/d2/f2.py", "d2/f3.py", "d2/d3/f4.py"])


if __name__ == "__main__":
  unittest.main()
