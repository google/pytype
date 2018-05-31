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


class Namespace(object):
  """Custom namespace for testing config.Postprocessor."""


class PostprocessorTest(unittest.TestCase):

  def setUp(self):
    self.input_options = Namespace()
    self.output_options = Namespace()

  def test_input(self):
    self.input_options.input = ["test.py"]
    config.Postprocessor(
        self.input_options, self.output_options, {"input"}).process()
    self.assertEqual(self.output_options.input, "test.py")

  def test_io_pair(self):
    self.input_options.input = ["in.py:out.pyi"]
    config.Postprocessor(
        self.input_options, self.output_options, {"input", "output"}).process()
    self.assertEqual(self.output_options.input, "in.py")
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_input(self):
    self.input_options.input = ["in.py:out.pyi"]
    # This argument should be ignored, since we're only processing the input.
    self.input_options.output = "out2.pyi"
    config.Postprocessor(
        self.input_options, self.output_options, {"input"}).process()
    self.assertEqual(self.output_options.input, "in.py")
    with self.assertRaises(AttributeError):
      _ = self.output_options.output

  def test_io_pair_output(self):
    self.input_options.input = ["in.py:out.pyi"]
    config.Postprocessor(
        self.input_options, self.output_options, {"output"}).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.input
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_multiple_output(self):
    self.input_options.input = ["in.py:out.pyi"]
    self.input_options.output = "out2.pyi"
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          self.input_options, self.output_options, {"output"}).process()

  def test_dependency(self):
    self.input_options.output = "test.pyi"
    self.input_options.check = None
    config.Postprocessor(
        self.input_options, self.output_options, {"output", "check"}).process()
    self.assertEqual(self.output_options.output, "test.pyi")
    self.assertIs(self.output_options.check, False)

  def test_subset(self):
    self.input_options.pythonpath = "."
    self.input_options.python_version = "3.4"
    config.Postprocessor(
        self.input_options, self.output_options, {"python_version"}).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.pythonpath  # not processed
    self.assertTupleEqual(self.output_options.python_version, (3, 4))

  def test_error(self):
    self.input_options.check = True
    self.input_options.output = "test.pyi"
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          self.input_options, self.output_options, {"check", "output"}
      ).process()


if __name__ == "__main__":
  unittest.main()
