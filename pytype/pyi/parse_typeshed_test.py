import os
import re
import sys

from pytype.pyi import parser
from pytype.pytd import typeshed

import unittest


# TODO(dbaum): A lot of this code was copied from pytd/typeshed_test.py.  Only
# one copy of the code will be necessary once the legacy parser is removed.


def _walk_dir(path):
  for root, _, filenames in os.walk(path):
    for f in filenames:
      yield os.path.join(root, f)


def _filename_to_testname(f):
  base = "stdlib"
  f = f[f.index(base) + len(base) + 1:].replace(os.sep, "_")
  return "test_" + os.path.splitext(f)[0]


def _test_parse(pyi_file):
  python_version = sys.version_info[:2]
  module = os.path.splitext(os.path.basename(pyi_file))[0]
  if module == "__init__":
    module = os.path.basename(os.path.dirname(pyi_file))
  with open(pyi_file) as f:
    src = f.read()
  parser.parse_string(src, filename=pyi_file, name=module,
                      python_version=python_version)


class TestTypeshedParsing(unittest.TestCase):
  """Test that we can parse a given pyi file."""
  # Files that we currently can't parse
  WANTED = re.compile(r"stdlib/(2\.7|2and3)/.*\.pyi$")
  t = typeshed.Typeshed()
  TYPESHED_DIR = t.root
  SKIPPED_FILES = list(t.read_blacklist())
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
