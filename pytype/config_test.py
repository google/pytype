"""Tests for config.py."""

from pytype import config
from pytype import datatypes

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


class PostprocessorTest(unittest.TestCase):

  def setUp(self):
    self.output_options = datatypes.SimpleNamespace()

  def test_input(self):
    input_options = datatypes.SimpleNamespace(input=["test.py"])
    config.Postprocessor(
        {"input"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "test.py")

  def test_io_pair(self):
    input_options = datatypes.SimpleNamespace(input=["in.py:out.pyi"])
    config.Postprocessor(
        {"input", "output"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "in.py")
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_input(self):
    # The duplicate output is ignored, since we're only processing the input.
    input_options = datatypes.SimpleNamespace(
        input=["in.py:out.pyi"], output="out2.pyi")
    config.Postprocessor(
        {"input"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "in.py")
    with self.assertRaises(AttributeError):
      _ = self.output_options.output

  def test_io_pair_output(self):
    input_options = datatypes.SimpleNamespace(input=["in.py:out.pyi"])
    config.Postprocessor(
        {"output"}, input_options, self.output_options).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.input
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_multiple_output(self):
    input_options = datatypes.SimpleNamespace(
        input=["in.py:out.pyi"], output="out2.pyi")
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          {"output"}, input_options, self.output_options).process()

  def test_dependency(self):
    input_options = datatypes.SimpleNamespace(output="test.pyi", check=None)
    config.Postprocessor(
        {"output", "check"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.output, "test.pyi")
    self.assertIs(self.output_options.check, False)

  def test_subset(self):
    input_options = datatypes.SimpleNamespace(
        pythonpath=".", python_version="3.4")
    config.Postprocessor(
        {"python_version"}, input_options, self.output_options).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.pythonpath  # not processed
    self.assertTupleEqual(self.output_options.python_version, (3, 4))

  def test_error(self):
    input_options = datatypes.SimpleNamespace(check=True, output="test.pyi")
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          {"check", "output"}, input_options, self.output_options).process()

  def test_inplace(self):
    input_options = datatypes.SimpleNamespace(
        disable="import-error,attribute-error", python_version="3.4")
    config.Postprocessor(
        {"disable", "python_version"}, input_options).process()
    self.assertSequenceEqual(
        input_options.disable, ["import-error", "attribute-error"])
    self.assertTupleEqual(input_options.python_version, (3, 4))


if __name__ == "__main__":
  unittest.main()
