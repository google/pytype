"""Tests for imports_map_loader.py."""

import tempfile

from pytype import imports_map_loader

import unittest


class ImportMapLoaderTest(unittest.TestCase):
  """Tests for imports_map_loader.py."""

  def testFilePaths(self):
    """Test the various permutations of output from FilePaths."""
    # Test both repr and str, in case there's still any test that depends
    # on the precise output form. Note that the output form is similar to
    # the args to _MakeFilePaths.
    for to_str_fn in repr, str:
      self.assertEqual(
          "FilePaths('abc.xyz')",
          to_str_fn(imports_map_loader.FilePaths(path="abc.xyz",
                                                 short_path="abc.xyz")))
      self.assertEqual(
          "FilePaths(short_path='mmm', path='abcdefg')",
          to_str_fn(imports_map_loader.FilePaths(short_path="mmm",
                                                 path="abcdefg")))
      self.assertEqual(
          "FilePaths('prefix/' + 'common' + '.suffix')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="prefix/common.suffix")))
      self.assertEqual(
          "FilePaths('prefix/' + 'common' + '')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="prefix/common")))
      self.assertEqual(
          "FilePaths('' + 'common' + '.suffix')",
          to_str_fn(imports_map_loader.FilePaths(short_path="common",
                                                 path="common.suffix")))
      # In the following, note the stuttered "path/to/"
      self.assertEqual(
          "FilePaths('GENFILES/path/to/' + 'path/to/src/b.py' + '~~pytype')",
          to_str_fn(imports_map_loader.FilePaths(
              short_path="path/to/src/b.py",
              path="GENFILES/path/to/path/to/src/b.py~~pytype")))
      self.assertEqual(
          "FilePaths('GENFILES/path/to/' + 'path/to/src/b.py' + '~~pytype')",
          to_str_fn(_MakeFilePaths(
              "GENFILES/path/to/",
              "path/to/src/b.py", "~~pytype")))

  def testReadImportsInfo(self):
    """Test reading an imports_info file into ImportsInfo."""
    with tempfile.NamedTemporaryFile() as fi:
      fi.write("""\
label "src/path/b_lib~~pytype"

pytype_srcs_filter_py "src/path/src/b.py" "src/path/src/b.py"


src_out_pairs_py "src/path/src/b.py" "GENFILES/src/path/#b_lib~~pytype.gen/src/path/src/b.py~~pytype"


pytype_provider_deps_files "src/path/src/__init__.py" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/__init__.py~~pytype"
pytype_provider_deps_files "src/path/src/b.py" "GENFILES/src/path/#b_lib~~pytype.gen/src/path/src/b.py~~pytype"
pytype_provider_deps_files "src/path/src/c.pytd" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c.pytd~~pytype"
pytype_provider_deps_files "src/path/src/c2.py" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c2.py~~pytype"
pytype_provider_deps_files "src/path/src2/d.py" "GENFILES/src/path/#d_lib~~pytype.gen/src/path/src2/d.py~~pytype"
pytype_provider_deps_files "src/path/src2/d2.py" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d2.py~~pytype"
pytype_provider_deps_files "src/path/src2/d3.py" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d3.py~~pytype"
pytype_provider_deps_files "src/path/src/c3.py" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c3.py~~pytype"

py_transitive_srcs "src/path/src/__init__.py" "src/path/src/__init__.py"
py_transitive_srcs "src/path/src/c.py" "src/path/src/c.py"
py_transitive_srcs "src/path/src/c2.py" "src/path/src/c2.py"
py_transitive_srcs "src/path/src2/d.py" "src/path/src2/d.py"
py_transitive_srcs "src/path/src2/d2.py" "src/path/src2/d2.py"
py_transitive_srcs "src/path/src2/d3.py" "src/path/src2/d3.py"
py_transitive_srcs "src/path/src/c3.py" "GENFILES/src/path/src/c3.py"

transitive_inputs "src/path/#c_lib~~pytype.gen/src/path/src/__init__.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/__init__.py~~pytype"
transitive_inputs "src/path/#c_lib~~pytype.gen/src/path/src/c.pytd~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c.pytd~~pytype"
transitive_inputs "src/path/#c_lib~~pytype.gen/src/path/src/c2.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c2.py~~pytype"
transitive_inputs "src/path/#d_lib~~pytype.gen/src/path/src2/d.py~~pytype" "GENFILES/src/path/#d_lib~~pytype.gen/src/path/src2/d.py~~pytype"
transitive_inputs "src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d2.py~~pytype" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d2.py~~pytype"
transitive_inputs "src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d3.py~~pytype" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d3.py~~pytype"
transitive_inputs "src/path/#c_lib~~pytype.gen/src/path/src/c3.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c3.py~~pytype"

py_deps "src/path/src2/d23_lib" "src/path/src2/d2.py" "src/path/src2/d2.py" "src/path/src2/d3.py" "src/path/src2/d3.py"
py_deps "src/path/c_lib" "src/path/src/__init__.py" "src/path/src/__init__.py" "src/path/src/c.py" "src/path/src/c.py" "src/path/src/c2.py" "src/path/src/c2.py" "src/path/src/c3.py" "GENFILES/src/path/src/c3.py"
py_deps "src/path/d_lib" "src/path/src2/d.py" "src/path/src2/d.py"

py_deps_files "src/path/src/__init__.py" "src/path/src/__init__.py"
py_deps_files "src/path/src/c.py" "src/path/src/c.py"
py_deps_files "src/path/src/c2.py" "src/path/src/c2.py"
py_deps_files "src/path/src2/d.py" "src/path/src2/d.py"
py_deps_files "src/path/src2/d2.py" "src/path/src2/d2.py"
py_deps_files "src/path/src2/d3.py" "src/path/src2/d3.py"
py_deps_files "src/path/src/c3.py" "GENFILES/src/path/src/c3.py"

pytype_deps_files "src/path/#c_lib~~pytype.gen/src/path/src/__init__.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/__init__.py~~pytype"
pytype_deps_files "src/path/#c_lib~~pytype.gen/src/path/src/c.pytd~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c.pytd~~pytype"
pytype_deps_files "src/path/#c_lib~~pytype.gen/src/path/src/c2.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c2.py~~pytype"
pytype_deps_files "src/path/#c_lib~~pytype.gen/src/path/src/c3.py~~pytype" "GENFILES/src/path/#c_lib~~pytype.gen/src/path/src/c3.py~~pytype"
pytype_deps_files "src/path/#d_lib~~pytype.gen/src/path/src2/d.py~~pytype" "GENFILES/src/path/#d_lib~~pytype.gen/src/path/src2/d.py~~pytype"
pytype_deps_files "src/path/c_lib~~pytype.imports_info" "GENFILES/src/path/c_lib~~pytype.imports_info"
pytype_deps_files "src/path/d_lib~~pytype.imports_info" "GENFILES/src/path/d_lib~~pytype.imports_info"
pytype_deps_files "src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d2.py~~pytype" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d2.py~~pytype"
pytype_deps_files "src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d3.py~~pytype" "GENFILES/src/path/src2/#d23_lib~~pytype.gen/src/path/src2/d3.py~~pytype"
pytype_deps_files "src/path/src2/d23_lib~~pytype.imports_info" "GENFILES/src/path/src2/d23_lib~~pytype.imports_info"
""")
      fi.seek(0)  # ready for reading
      self.assertEqual(
          imports_map_loader._read_pytype_provider_deps_files(fi.name),
          frozenset([
              _MakeFilePaths("GENFILES/src/path/#b_lib~~pytype.gen/", "src/path/src/b.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/#c_lib~~pytype.gen/", "src/path/src/__init__.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/#c_lib~~pytype.gen/", "src/path/src/c.pytd", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/#c_lib~~pytype.gen/", "src/path/src/c2.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/#c_lib~~pytype.gen/", "src/path/src/c3.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/#d_lib~~pytype.gen/", "src/path/src2/d.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/src2/#d23_lib~~pytype.gen/", "src/path/src2/d2.py", "~~pytype"),
              _MakeFilePaths("GENFILES/src/path/src2/#d23_lib~~pytype.gen/", "src/path/src2/d3.py", "~~pytype"),
              ]))


def _MakeFilePaths(prefix, common, suffix):
  return imports_map_loader.FilePaths(path=prefix + common + suffix,
                                      short_path=common)


if __name__ == "__main__":
  unittest.main()
