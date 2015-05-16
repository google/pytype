"""Tests for import_paths.py."""


from pytype import import_paths
from pytype.tests import test_inference

import unittest


class ImportPathsTest(unittest.TestCase):
  """Tests for import_paths.py."""

  PYTHON_VERSION = (2, 7)

  def testBuiltinSys(self):
    # TODO(pludemann): test with non-empty pythonpath
    pytd = import_paths.module_name_to_pytd("sys", 0, self.PYTHON_VERSION,
                                            pythonpath=[])
    self.assertTrue(pytd)
    self.assertTrue(pytd.Lookup("exit"))


if __name__ == "__main__":
  test_inference.main()
