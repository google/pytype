"""Tests for config.py."""

from pytype import config

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

  def test_analyze_annotated_check(self):
    argv = ["pytype", "--check", "test.py"]
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)

  def test_analyze_annotated_output(self):
    argv = ["pytype", "--output=out.pyi", "test.py"]
    opts = config.Options(argv)
    self.assertFalse(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)


if __name__ == "__main__":
  unittest.main()
