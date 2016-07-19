"""Tests for typeshed.py."""

import os
import re


from pytype.pytd import typeshed
from pytype.pytd import utils
from pytype.pytd.parse import parser_test_base
import unittest


class TestTypeshedLoading(parser_test_base.ParserTest):
  """Test the code for loading files from typeshed."""

  def test_get_typeshed_file(self):
    filename, data = typeshed.get_typeshed_file("stdlib", "errno", (2, 7))
    self.assertEqual("errno.pyi", os.path.basename(filename))
    self.assertIn("errorcode", data)

  def test_get_typeshed_dir(self):
    filename, data = typeshed.get_typeshed_file("stdlib", "logging", (2, 7))
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
  # Call ParsePyTD directly to avoid typeshed.get_typeshed_file logic
  utils.ParsePyTD(src,
                  filename=pyi_file,
                  module=module,
                  python_version=python_version)


class TestTypeshedParsing(parser_test_base.ParserTest):
  """Test that we can parse a given pyi file."""
  # Files that we currently can't parse
  SKIPPED_FILES = """
      2.7/Cookie.pyi
      2.7/StringIO.pyi
      2.7/__builtin__.pyi
      2.7/argparse.pyi
      2.7/builtins.pyi
      2.7/calendar.pyi
      2.7/codecs.pyi
      2.7/email/utils.pyi
      2.7/functools.pyi
      2.7/inspect.pyi
      2.7/logging/__init__.pyi
      2.7/os/__init__.pyi
      2.7/platform.pyi
      2.7/rfc822.pyi
      2.7/simplejson/__init__.pyi
      2.7/socket.pyi
      2.7/sqlite3/dbapi2.pyi
      2.7/ssl.pyi
      2.7/threading.pyi
      2.7/types.pyi
      2.7/typing.pyi
      2.7/unittest.pyi
      2.7/urllib2.pyi
      2.7/xml/etree/ElementInclude.pyi
      2.7/xml/etree/ElementPath.pyi
      2and3/cmath.pyi
      2and3/logging/__init__.pyi
      2and3/logging/config.pyi
      2and3/logging/handlers.pyi
      2and3/math.pyi
      2and3/warnings.pyi
      2and3/webbrowser.pyi
  """
  WANTED = re.compile(r"stdlib/(2\.7|2and3)/.*\.pyi$")
  SKIPPED = re.compile("(%s)$" % "|".join(SKIPPED_FILES.split()))
  TYPESHED_DIR = typeshed.get_typeshed_dir()

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
