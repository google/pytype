"""Tests for imports_map_loader.py."""

import tempfile

from pytype import imports_map_loader

import unittest


class ImportMapLoaderTest(unittest.TestCase):
  """Tests for imports_map_loader.py."""

  def testModulePathAndPyiPath(self):
    """Test the various permutations of output from ModulePathAndPyiPath."""
    # Test both repr and str, in case there's still any test that depends
    # on the precise output form. Note that the output form is similar to
    # the args to _MakeModulePathAndPyiPath.
    for to_str_fn in repr, str:
      self.assertEqual(
          "['abc.xyz']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              path="abc.xyz", short_path="abc.xyz")))
      self.assertEqual(
          "['mmm' -> 'abcdefg']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              short_path="mmm", path="abcdefg")))
      self.assertEqual(
          "['prefix/' + 'common' + '.suffix']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              short_path="common", path="prefix/common.suffix")))
      self.assertEqual(
          "['prefix/' + 'common' + '']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              short_path="common", path="prefix/common")))
      self.assertEqual(
          "['' + 'common' + '.suffix']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              short_path="common", path="common.suffix")))
      # In the following, note the stuttered "path/to/"
      self.assertEqual(
          "['GENFILES/path/to/' + 'path/to/src/b.py' + '~~pytype']",
          to_str_fn(imports_map_loader.ModulePathAndPyiPath(
              short_path="path/to/src/b.py",
              path="GENFILES/path/to/path/to/src/b.py~~pytype")))
      self.assertEqual(
          "['GENFILES/path/to/' + 'path/to/src/b.py' + '~~pytype']",
          to_str_fn(_MakeModulePathAndPyiPath(
              "GENFILES/path/to/",
              "path/to/src/b.py", "~~pytype")))

  def testReadImportsInfo(self):
    """Test reading an imports_info file into ImportsInfo."""
    with tempfile.NamedTemporaryFile() as fi:
      fi.write("""
"a/b/__init__.py" "prefix/1/a/b/__init__.py~"
"a/b/b.py" "prefix/1/a/b/b.py~suffix"
"a/b/c.pyi" "prefix/1/a/b/c.pyi~"
a/b/d.py "prefix/1/a/b/d.py~"
"a/b/2/d2.py" "prefix/2/a/b/2/d2.py~"
"a/b/2/d3.py" "prefix/2/a/b/2/d3.py~"
""")
      fi.seek(0)  # ready for reading
      self.assertSameElements(
          imports_map_loader._read_pytype_provider_deps_files(fi.name),
          [
              _MakeModulePathAndPyiPath("prefix/1/", "a/b/__init__.py", "~"),
              _MakeModulePathAndPyiPath("prefix/1/", "a/b/b.py", "~suffix"),
              _MakeModulePathAndPyiPath("prefix/1/", "a/b/c.pyi", "~"),
              _MakeModulePathAndPyiPath("prefix/1/", "a/b/d.py", "~"),
              _MakeModulePathAndPyiPath("prefix/2/", "a/b/2/d2.py", "~"),
              _MakeModulePathAndPyiPath("prefix/2/", "a/b/2/d3.py", "~"),
          ])


def _MakeModulePathAndPyiPath(prefix, common, suffix):
  return imports_map_loader.ModulePathAndPyiPath(path=prefix + common + suffix,
                                                 short_path=common)


if __name__ == "__main__":
  unittest.main()
