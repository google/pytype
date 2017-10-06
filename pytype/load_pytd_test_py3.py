"""Tests for load_pytd.py."""


from pytype import config
from pytype import load_pytd
from pytype import utils
from pytype.pytd import pytd

import unittest

# Since builtins.py has a global cache for the typing module, the python3 tests
# need to be in a separate file from the python2 ones.


class Python3Test(unittest.TestCase):
  """Tests for load_pytd.py."""

  PYTHON_VERSION = (3, 6)

  def setUp(self):
    self.options = config.Options.create(python_version=self.PYTHON_VERSION)

  def testPython3Builtins(self):
    # Test that we read python3 builtins from builtin.pytd if we pass a (3, 6)
    # version to the loader.
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """\
          from typing import AsyncGenerator
          class A(AsyncGenerator[str]): ...""")
      self.options.tweak(pythonpath=[d.path])
      loader = load_pytd.Loader("base", self.options)
      a = loader.import_name("a")
      cls = a.Lookup("a.A")
      # New python3 builtins are currently aliases for Any.
      self.assertTrue(pytd.AnythingType() in cls.parents)


if __name__ == "__main__":
  unittest.main()
