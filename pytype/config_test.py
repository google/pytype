"""Tests for config.py."""

from pytype import config

import unittest


class ConfigTest(unittest.TestCase):

  def test_basic(self):
    argv = [
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
    argv = ["--check", "test.py"]
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)

  def test_analyze_annotated_output(self):
    argv = ["--output=out.pyi", "test.py"]
    opts = config.Options(argv)
    self.assertFalse(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv)
    self.assertTrue(opts.analyze_annotated)

  def test_bad_verbosity(self):
    argv = ["--verbosity", "5", "test.py"]
    with self.assertRaises(SystemExit):
      config.Options(argv)

  def _test_arg_conflict(self, arg1, arg2):
    argv = [arg1, arg2, "test.py"]
    with self.assertRaises(SystemExit):
      config.Options(argv)

  def test_arg_conflicts(self):
    for arg1, arg2 in [
        ("--check", "--output=foo"),
        ("--output-errors-csv=foo", "--no-report-errors"),
        ("--output-cfg=foo", "--output-typegraph=bar"),
        ("--pythonpath=foo", "--imports_info=bar")
    ]:
      self._test_arg_conflict(arg1, arg2)


if __name__ == "__main__":
  unittest.main()
