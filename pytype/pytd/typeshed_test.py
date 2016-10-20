"""Tests for typeshed.py."""

import os
import re


from pytype.pytd import typeshed
from pytype.pytd.parse import builtins
from pytype.pytd.parse import parser_test_base
import unittest


class TestTypeshedLoading(parser_test_base.ParserTest):
  """Test the code for loading files from typeshed."""

  def setUp(self):
    super(TestTypeshedLoading, self).setUp()
    self.ts = typeshed.Typeshed()

  def test_get_typeshed_file(self):
    filename, data = self.ts.get_module_file("stdlib", "errno", (2, 7))
    self.assertEqual("errno.pyi", os.path.basename(filename))
    self.assertIn("errorcode", data)

  def test_get_typeshed_dir(self):
    filename, data = self.ts.get_module_file("stdlib", "logging", (2, 7))
    self.assertEqual("__init__.pyi", os.path.basename(filename))
    self.assertIn("LogRecord", data)

  def test_parse_type_definition(self):
    ast = typeshed.parse_type_definition("stdlib", "_random", (2, 7))
    self.assertIn("_random.Random", [cls.name for cls in ast.classes])



def _walk_dir(path):
  for root, _, filenames in os.walk(path):
    for f in filenames:
      yield os.path.join(root, f)


def _filename_to_testname(f):
  base = "stdlib"
  f = f[f.index(base) + len(base) + 1:].replace(os.sep, "_")
  return "test_" + os.path.splitext(f)[0]


def _test_parse(pyi_file):
  python_version = (2, 7)
  module = os.path.splitext(os.path.basename(pyi_file))[0]
  if "__init__" == module:
    module = os.path.basename(os.path.dirname(pyi_file))
  with open(pyi_file) as f:
    src = f.read()
  # Call ParsePyTD directly to avoid Typeshed.get_module_file logic
  builtins.ParsePyTD(src,
                     filename=pyi_file,
                     module=module,
                     python_version=python_version)


def _read_blacklist(typeshed_dir):
  with open(os.path.join(typeshed_dir, "tests/pytype_blacklist.txt")) as fi:
    for line in fi:
      line = line[:line.find("#")].strip()
      if line:
        yield line


class TestTypeshedParsing(parser_test_base.ParserTest):
  """Test that we can parse a given pyi file."""
  # Files that we currently can't parse
  WANTED = re.compile(r"stdlib/(2\.7|2and3)/.*\.pyi$")
  TYPESHED_DIR = typeshed.Typeshed().typeshed_path
  SKIPPED_FILES = list(_read_blacklist(TYPESHED_DIR))
  SKIPPED = re.compile("(%s)$" % "|".join(SKIPPED_FILES))

  # Generate test methods
  # pylint: disable=no-self-argument,g-wrong-blank-lines,undefined-loop-variable
  for f in _walk_dir(TYPESHED_DIR):
    if WANTED.search(f) and not SKIPPED.search(f):
      def _bind(f):
        return lambda self: _test_parse(f)
      locals()[_filename_to_testname(f)] = _bind(f)
      del _bind
  del f


if __name__ == "__main__":
  unittest.main()
