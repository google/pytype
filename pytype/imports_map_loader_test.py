"""Tests for imports_map_loader.py."""

import tempfile

from pytype import imports_map_loader

import unittest


class ImportMapLoaderTest(unittest.TestCase):
  """Tests for imports_map_loader.py."""

  def testReadImportsInfo(self):
    """Test reading an imports_info file into ImportsInfo."""
    with tempfile.NamedTemporaryFile() as fi:
      fi.write("""
"a/b/__init__.py" "prefix/1/a/b/__init__.py~"
"a/b/b.py" "prefix/1/a/b/b.py~suffix"
"a/b/c.pyi" "prefix/1/a/b/c.pyi~"
a/b/d.py "prefix/1/a/b/d.py~"
"a/b/e.py" "2/a/b/e1.py~"
"a/b/e" "2/a/b/e2.py~"
"a/b/e" "2/a/b/foo/#2.py~"
""")
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


if __name__ == "__main__":
  unittest.main()
