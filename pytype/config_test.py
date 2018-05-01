"""Tests for config.py."""

from pytype import config
from pytype.tests import test_base

import unittest


class ConfigTest(unittest.TestCase):

  def test_basic(self):
    argv = [
        "pytype",
        "-V", "3.6",
        "--use-pickled-files",
        "-o", "out.pyi",
        "--pythonpath", "foo:bar",
        "test.py"
    ]
    opts = config.Options(argv)
    self.assertEqual(opts.python_version, (3, 6))
    self.assertEqual(opts.use_pickled_files, True)
    self.assertEqual(opts.pythonpath, ["foo", "bar"])
    self.assertEqual(opts.output, "out.pyi")
    self.assertEqual(opts.input, "test.py")


if __name__ == "__main__":
  test_base.main()
