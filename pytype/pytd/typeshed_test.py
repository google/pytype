"""Tests for typeshed.py."""

import os
import re
import unittest


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


class _TestTypeshedParsing(parser_test_base.ParserTest):
  """Test that we can parse a given pyi file."""
  # Files that we currently can't parse
  SKIPPED_FILES = """
      2.7/Cookie.pyi
      2.7/SocketServer.pyi
      2.7/StringIO.pyi
      2.7/__builtin__.pyi
      2.7/__future__.pyi
      2.7/argparse.pyi
      2.7/builtins.pyi
      2.7/calendar.pyi
      2.7/codecs.pyi
      2.7/collections.pyi
      2.7/csv.pyi
      2.7/email/utils.pyi
      2.7/functools.pyi
      2.7/inspect.pyi
      2.7/logging/__init__.pyi
      2.7/os/__init__.pyi
      2.7/platform.pyi
      2.7/resource.pyi
      2.7/rfc822.pyi
      2.7/simplejson/__init__.pyi
      2.7/socket.pyi
      2.7/sqlite3/dbapi2.pyi
      2.7/ssl.pyi
      2.7/subprocess.pyi
      2.7/threading.pyi
      2.7/time.pyi
      2.7/token.pyi
      2.7/types.pyi
      2.7/typing.pyi
      2.7/unittest.pyi
      2.7/urllib2.pyi
      2.7/urlparse.pyi
      2.7/uuid.pyi
      2.7/xml/etree/ElementInclude.pyi
      2.7/xml/etree/ElementPath.pyi
      2.7/xml/etree/ElementTree.pyi
      2and3/cmath.pyi
      2and3/logging/__init__.pyi
      2and3/logging/config.pyi
      2and3/logging/handlers.pyi
      2and3/math.pyi
      2and3/webbrowser.pyi
  """

  def __init__(self, pyi_file):
    super(_TestTypeshedParsing, self).__init__("run_test")
    self.pyi_file = pyi_file

  def run_test(self):
    python_version = (2, 7)
    module = os.path.splitext(os.path.basename(self.pyi_file))[0]
    if "__init__" == module:
      module = os.path.basename(os.path.dirname(self.pyi_file))

    with open(self.pyi_file) as f:
      src = f.read()

    # Call ParsePyTD directly to avoid typeshed.get_typeshed_file logic
    utils.ParsePyTD(src,
                    filename=self.pyi_file,
                    module=module,
                    python_version=python_version)


def _walk_dir(path):
  for root, _, filenames in os.walk(path):
    for f in filenames:
      yield os.path.join(root, f)


def load_tests(unused_loader, standard_tests, unused_pattern):
  # Only testing against part of typeshed
  wanted = re.compile(r"stdlib/(2\.7|2and3)/.*\.pyi$")
  skipped = re.compile("(%s)$" % "|".join(
      _TestTypeshedParsing.SKIPPED_FILES.split()))

  found_tests = False
  typeshed_dir = typeshed.get_typeshed_dir()
  suite = unittest.unittest.TestSuite(standard_tests)
  for f in _walk_dir(typeshed_dir):
    if wanted.search(f) and not skipped.search(f):
      suite.addTest(_TestTypeshedParsing(f))
      found_tests = True

  assert found_tests
  return suite


if __name__ == "__main__":
  unittest.main()
