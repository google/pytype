import gc
import os
import sys

from pytype.pyi import parser
from pytype.pytd import pytd
from pytype.tests import test_base
import six

import unittest


def get_builtins_source(python_version):
  filename = "builtins/%d/__builtin__.pytd" % python_version[0]
  pytd_dir = os.path.dirname(pytd.__file__)
  with open(os.path.join(pytd_dir, filename)) as f:
    return f.read()


class MemoryLeakTest(test_base.UnitTest):

  def check(self, src):
    def parse():
      try:
        parser.parse_string(src, python_version=self.python_version)
      except parser.ParseError:
        if six.PY2:
          # It is essential to clear the error, otherwise the system exc_info
          # will hold references to lots of stuff hanging off the exception.
          # This happens only in Python2.
          sys.exc_clear()

    # Sometimes parsing has side effects that are long-lived (lazy
    # initialization of shared instances, etc).  In order to prevent these
    # from looking like leaks, parse the source twice, using the gc objects
    # after the first pass as a baseline for the second pass.
    parse()
    gc.collect()
    before = gc.get_objects()
    parse()
    gc.collect()
    after = gc.get_objects()

    # Determine the ids of any leaked objects.
    before_ids = {id(x) for x in before}
    after_map = {id(x): x for x in after}
    leaked_ids = set(after_map) - before_ids
    leaked_ids.discard(id(before))
    if not leaked_ids:
      return

    # Include details about the leaked objects in the failure message.
    lines = ["Detected %d leaked objects" % len(leaked_ids)]
    for i in leaked_ids:
      obj = after_map[i]
      detail = str(obj)
      if len(detail) > 50:
        detail = detail[:50] + "..."
      lines.append("  <%s>  %s" % (type(obj).__name__, detail))
    self.fail("\n".join(lines))

  def test_builtins(self):
    # This has a little of everything.
    self.check(get_builtins_source(self.python_version))

  def test_error_in_class(self):
    self.check("""
      class Foo:
        def m(): pass
        an error""")

  def test_error_in_function(self):
    self.check("""
      def m(): pass
      def n(x: int, y: str) -> ->
      """)

  def test_error_within_if(self):
    self.check("""
      if sys.version_info == (1, 2, 3):
        x = ...  # type: int
        this is an error
      """)


if __name__ == "__main__":
  unittest.main()
