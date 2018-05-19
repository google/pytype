"""Tests for imports_map_loader.py."""

import os
import tempfile
import textwrap

from pytype import compat
from pytype import file_utils
from pytype import imports_map_loader

import unittest


class ImportMapLoaderTest(unittest.TestCase):
  """Tests for imports_map_loader.py."""

  def testReadImportsInfo(self):
    """Test reading an imports_info file into ImportsInfo."""
    with tempfile.NamedTemporaryFile() as fi:
      fi.write(compat.bytestring(textwrap.dedent("""
        a/b/__init__.py prefix/1/a/b/__init__.py~
        a/b/b.py prefix/1/a/b/b.py~suffix
        a/b/c.pyi prefix/1/a/b/c.pyi~
        a/b/d.py prefix/1/a/b/d.py~
        a/b/e.py 2/a/b/e1.py~
        a/b/e 2/a/b/e2.py~
        a/b/e 2/a/b/foo/#2.py~
      """)))
      fi.seek(0)  # ready for reading
      self.assertSameElements(
          imports_map_loader._read_imports_map(fi.name).items(),
          [
              ("a/b/__init__", ["prefix/1/a/b/__init__.py~"]),
              ("a/b/b", ["prefix/1/a/b/b.py~suffix"]),
              ("a/b/c", ["prefix/1/a/b/c.pyi~"]),
              ("a/b/d", ["prefix/1/a/b/d.py~"]),
              ("a/b/e", ["2/a/b/foo/#2.py~", "2/a/b/e1.py~", "2/a/b/e2.py~"]),
          ])

  def testImportsInfoFilter(self):
    """Test filtering out the current target's entry from the imports info."""
    with file_utils.Tempdir() as d:
      # The files in our "program" that we're building an imports_map for.
      files = [
          "a/__init__.py",
          "a/b.py",
      ]
      # The files the previous files are mapped to:
      imports = ["prefix{0}/{1}~suffix".format(d.path, f) for f in files]
      # Since we're calling _validate_map (via build_imports_map), the files
      # have to actually exist.
      for f in files + imports:
        d.create_file(f, "")
      # We have to add the path so the import map contains the actual files as
      # they exist in the tempdir.
      imports_map = ["%s %s" % (d[f], d[t]) for f, t in zip(files, imports)]
      d.create_file("imports_info", "\n".join(imports_map))
      # build_imports_map should strip out the entry for a/__init__.py, leaving
      # the entry for a/b.py intact.
      self.assertSameElements(
          imports_map_loader.build_imports_map(d["imports_info"],
                                               d["a/__init__.py"]).items(),
          [
              ("%s/a/b" % d.path, "{0}/prefix{0}/a/b.py~suffix".format(d.path)),
              # These are all added by the last bit of build_imports_map
              ("__init__", os.devnull),
              ("tmp/__init__", os.devnull),
              ("%s/__init__" % d.path[1:], os.devnull),
              ("%s/a/__init__" % d.path[1:], os.devnull),
          ]
      )

if __name__ == "__main__":
  unittest.main()
