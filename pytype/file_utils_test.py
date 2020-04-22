"""Tests for file_utils.py."""

import os

from pytype import file_utils
import six

import unittest


class FileUtilsTest(unittest.TestCase):
  """Test file and path utilities."""

  def test_replace_extension(self):
    self.assertEqual("foo.bar", file_utils.replace_extension("foo.txt", "bar"))
    self.assertEqual("foo.bar", file_utils.replace_extension("foo.txt", ".bar"))
    self.assertEqual("a.b.c.bar",
                     file_utils.replace_extension("a.b.c.txt", ".bar"))
    self.assertEqual("a.b/c.bar",
                     file_utils.replace_extension("a.b/c.d", ".bar"))
    self.assertEqual("xyz.bar", file_utils.replace_extension("xyz", "bar"))

  def test_tempdir(self):
    with file_utils.Tempdir() as d:
      filename1 = d.create_file("foo.txt")
      filename2 = d.create_file("bar.txt", "\tdata2")
      filename3 = d.create_file("baz.txt", "data3")
      filename4 = d.create_file("d1/d2/qqsv.txt", "  data4.1\n  data4.2")
      filename5 = d.create_directory("directory")
      self.assertEqual(filename1, d["foo.txt"])
      self.assertEqual(filename2, d["bar.txt"])
      self.assertEqual(filename3, d["baz.txt"])
      self.assertEqual(filename4, d["d1/d2/qqsv.txt"])
      self.assertTrue(os.path.isdir(d.path))
      self.assertTrue(os.path.isfile(filename1))
      self.assertTrue(os.path.isfile(filename2))
      self.assertTrue(os.path.isfile(filename3))
      self.assertTrue(os.path.isfile(filename4))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1")))
      self.assertTrue(os.path.isdir(os.path.join(d.path, "d1", "d2")))
      self.assertTrue(os.path.isdir(filename5))
      self.assertEqual(filename4, os.path.join(d.path, "d1", "d2", "qqsv.txt"))
      for filename, contents in [(filename1, ""),
                                 (filename2, "data2"),  # dedented
                                 (filename3, "data3"),
                                 (filename4, "data4.1\ndata4.2"),  # dedented
                                ]:
        with open(filename, "r") as fi:
          self.assertEqual(fi.read(), contents)
    self.assertFalse(os.path.isdir(d.path))
    self.assertFalse(os.path.isfile(filename1))
    self.assertFalse(os.path.isfile(filename2))
    self.assertFalse(os.path.isfile(filename3))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1")))
    self.assertFalse(os.path.isdir(os.path.join(d.path, "d1", "d2")))
    self.assertFalse(os.path.isdir(filename5))

  def test_cd(self):
    with file_utils.Tempdir() as d:
      d.create_directory("foo")
      d1 = os.getcwd()
      with file_utils.cd(d.path):
        self.assertTrue(os.path.isdir("foo"))
      d2 = os.getcwd()
      self.assertEqual(d1, d2)

  def test_cd_noop(self):
    d = os.getcwd()
    with file_utils.cd(None):
      self.assertEqual(os.getcwd(), d)
    with file_utils.cd(""):
      self.assertEqual(os.getcwd(), d)


class TestPathExpansion(unittest.TestCase):
  """Tests for file_utils.expand_path(s?)."""

  def test_expand_one_path(self):
    full_path = os.path.join(os.getcwd(), "foo.py")
    self.assertEqual(file_utils.expand_path("foo.py"), full_path)

  def test_expand_two_paths(self):
    full_path1 = os.path.join(os.getcwd(), "foo.py")
    full_path2 = os.path.join(os.getcwd(), "bar.py")
    self.assertEqual(file_utils.expand_paths(["foo.py", "bar.py"]),
                     [full_path1, full_path2])

  def test_expand_with_cwd(self):
    with file_utils.Tempdir() as d:
      f = d.create_file("foo.py")
      self.assertEqual(file_utils.expand_path("foo.py", d.path), f)


class TestExpandSourceFiles(unittest.TestCase):
  """Tests for file_utils.expand_source_files."""

  FILES = [
      "a.py", "foo/b.py", "foo/c.txt", "foo/bar/d.py",
      "foo/bar/baz/e.py"
  ]

  def _test_expand(self, string):
    with file_utils.Tempdir() as d:
      fs = [d.create_file(f) for f in self.FILES]
      pyfiles = [f for f in fs if f.endswith(".py")]
      six.assertCountEqual(
          self,
          pyfiles,
          file_utils.expand_source_files(string, d.path))

  def test_expand_source_files(self):
    self._test_expand("a.py foo/c.txt foo")

  def test_duplicates(self):
    self._test_expand("a.py foo/b.py foo foo/bar")

  def test_cwd(self):
    with file_utils.Tempdir() as d:
      fs = [d.create_file(f) for f in self.FILES]
      pyfiles = [f for f in fs if f.endswith(".py")]
      # cd to d.path and run with just "." as an argument
      with file_utils.cd(d.path):
        six.assertCountEqual(
            self, pyfiles, file_utils.expand_source_files("."))

  def test_empty(self):
    self.assertEqual(file_utils.expand_source_files(""), set())

  def test_magic(self):
    filenames = ["a.py", "b/c.py"]
    with file_utils.Tempdir() as d:
      for f in filenames:
        d.create_file(f)
      with file_utils.cd(d.path):
        self.assertEqual(file_utils.expand_source_files("**/*.py"),
                         {os.path.realpath(f) for f in filenames})

  def test_magic_with_cwd(self):
    filenames = ["a.py", "b/c.py"]
    with file_utils.Tempdir() as d:
      for f in filenames:
        d.create_file(f)
      self.assertEqual(file_utils.expand_source_files("**/*.py", cwd=d.path),
                       {os.path.join(d.path, f) for f in filenames})

  def test_multiple_magic(self):
    filenames = ["a.py", "b/c.py"]
    with file_utils.Tempdir() as d:
      for f in filenames:
        d.create_file(f)
      self.assertEqual(
          file_utils.expand_source_files("*.py b/*.py", cwd=d.path),
          {os.path.join(d.path, f) for f in filenames})


class TestExpandHiddenFiles(unittest.TestCase):

  def test_ignore_file(self):
    with file_utils.Tempdir() as d:
      d.create_file(".ignore.py")
      self.assertEqual(file_utils.expand_source_files(".", cwd=d.path), set())

  def test_find_file(self):
    with file_utils.Tempdir() as d:
      d.create_file(".find.py")
      self.assertEqual(file_utils.expand_source_files(".*", cwd=d.path),
                       {os.path.join(d.path, ".find.py")})

  def test_ignore_dir(self):
    with file_utils.Tempdir() as d:
      d.create_file("d1/.d2/ignore.py")
      self.assertEqual(
          file_utils.expand_source_files("d1/**/*", cwd=d.path), set())

  def test_find_dir(self):
    with file_utils.Tempdir() as d:
      d.create_file(".d/find.py")
      self.assertEqual(file_utils.expand_source_files(".d/**/*", cwd=d.path),
                       {os.path.join(d.path, ".d", "find.py")})


class TestExpandPythonpath(unittest.TestCase):

  def test_expand(self):
    self.assertEqual(file_utils.expand_pythonpath("a/b%sc/d" % os.pathsep),
                     [os.path.join(os.getcwd(), "a", "b"),
                      os.path.join(os.getcwd(), "c", "d")])

  def test_expand_empty(self):
    self.assertEqual(file_utils.expand_pythonpath(""), [])

  def test_expand_current_directory(self):
    self.assertEqual(file_utils.expand_pythonpath("%sa" % os.pathsep),
                     [os.getcwd(), os.path.join(os.getcwd(), "a")])

  def test_expand_with_cwd(self):
    with file_utils.Tempdir() as d:
      self.assertEqual(
          file_utils.expand_pythonpath("a/b%sc/d" % os.pathsep, cwd=d.path),
          [os.path.join(d.path, "a", "b"), os.path.join(d.path, "c", "d")])

  def test_strip_whitespace(self):
    self.assertEqual(file_utils.expand_pythonpath("""
      a/b:
      c/d
    """), [os.path.join(os.getcwd(), "a", "b"),
           os.path.join(os.getcwd(), "c", "d")])


class TestExpandGlobpaths(unittest.TestCase):

  def test_expand_empty(self):
    self.assertEqual(file_utils.expand_globpaths([]), [])

  def test_expand(self):
    filenames = ["a.py", "b/c.py"]
    with file_utils.Tempdir() as d:
      for f in filenames:
        d.create_file(f)
      with file_utils.cd(d.path):
        self.assertEqual(file_utils.expand_globpaths(["**/*.py"]),
                         [os.path.realpath(f) for f in filenames])

  def test_expand_with_cwd(self):
    filenames = ["a.py", "b/c.py"]
    with file_utils.Tempdir() as d:
      for f in filenames:
        d.create_file(f)
      self.assertEqual(file_utils.expand_globpaths(["**/*.py"], cwd=d.path),
                       [os.path.join(d.path, f) for f in filenames])


if __name__ == "__main__":
  unittest.main()
