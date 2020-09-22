"""Tests for config.py."""

import logging
import sys
import types

from pytype import config
from pytype import utils

import unittest


class ConfigTest(unittest.TestCase):

  def test_basic(self):
    version = sys.version_info[:2]
    argv = [
        "-V", utils.format_version(version),
        "--use-pickled-files",
        "-o", "out.pyi",
        "--pythonpath", "foo:bar",
        "test.py"
    ]
    opts = config.Options(argv, command_line=True)
    self.assertEqual(opts.python_version, version)
    self.assertEqual(opts.use_pickled_files, True)
    self.assertEqual(opts.pythonpath, ["foo", "bar"])
    self.assertEqual(opts.output, "out.pyi")
    self.assertEqual(opts.input, "test.py")

  def test_create(self):
    version = sys.version_info[:2]
    opts = config.Options.create(
        input_filename="foo.py", python_version=utils.format_version(version),
        use_pickled_files=True)
    self.assertEqual(opts.input, "foo.py")
    self.assertEqual(opts.use_pickled_files, True)
    self.assertEqual(opts.python_version, version)
    exe, _ = opts.python_exe
    self.assertIsNone(exe)

    opts = config.Options.create(python_version=(2, 7), use_pickled_files=True)
    self.assertEqual(opts.use_pickled_files, True)
    self.assertEqual(opts.python_version, (2, 7))
    (exe,), _ = opts.python_exe
    self.assertIn("2.7", exe)

  def test_analyze_annotated_check(self):
    argv = ["--check", "test.py"]
    opts = config.Options(argv, command_line=True)
    self.assertTrue(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv, command_line=True)
    self.assertTrue(opts.analyze_annotated)

  def test_analyze_annotated_output(self):
    argv = ["--output=out.pyi", "test.py"]
    opts = config.Options(argv, command_line=True)
    self.assertFalse(opts.analyze_annotated)  # default
    argv.append("--analyze-annotated")
    opts = config.Options(argv, command_line=True)
    self.assertTrue(opts.analyze_annotated)

  def test_verbosity(self):
    level = logging.getLogger().getEffectiveLevel()
    # make sure we properly exercise verbosity_from by changing the log level
    assert level != logging.ERROR
    with config.verbosity_from(config.Options.create(verbosity=1)):
      self.assertEqual(logging.getLogger().getEffectiveLevel(), logging.ERROR)
    self.assertEqual(logging.getLogger().getEffectiveLevel(), level)

  def test_bad_verbosity(self):
    argv = ["--verbosity", "5", "test.py"]
    with self.assertRaises(SystemExit):
      config.Options(argv, command_line=True)

  def test_bad_verbosity_create(self):
    with self.assertRaises(config.PostprocessingError):
      config.Options.create("test.py", verbosity=5)

  def _test_arg_conflict(self, arg1, arg2):
    argv = [arg1, arg2, "test.py"]
    with self.assertRaises(SystemExit):
      config.Options(argv, command_line=True)

  def test_arg_conflicts(self):
    for arg1, arg2 in [
        ("--check", "--output=foo"),
        ("--output-errors-csv=foo", "--no-report-errors"),
        ("--output-cfg=foo", "--output-typegraph=bar"),
        ("--pythonpath=foo", "--imports_info=bar")
    ]:
      self._test_arg_conflict(arg1, arg2)

  def test_bad_construction(self):
    with self.assertRaises(TypeError):
      # To prevent accidental misuse, command_line must be explicitly set when
      # directly constructing Options.
      config.Options([])


class PostprocessorTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.output_options = types.SimpleNamespace()

  def test_input(self):
    input_options = types.SimpleNamespace(input=["test.py"])
    config.Postprocessor(
        {"input"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "test.py")

  def test_io_pair(self):
    input_options = types.SimpleNamespace(input=["in.py:out.pyi"])
    config.Postprocessor(
        {"input", "output"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "in.py")
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_input(self):
    # The duplicate output is ignored, since we're only processing the input.
    input_options = types.SimpleNamespace(
        input=["in.py:out.pyi"], output="out2.pyi")
    config.Postprocessor(
        {"input"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.input, "in.py")
    with self.assertRaises(AttributeError):
      _ = self.output_options.output

  def test_io_pair_output(self):
    input_options = types.SimpleNamespace(input=["in.py:out.pyi"])
    config.Postprocessor(
        {"output"}, input_options, self.output_options).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.input
    self.assertEqual(self.output_options.output, "out.pyi")

  def test_io_pair_multiple_output(self):
    input_options = types.SimpleNamespace(
        input=["in.py:out.pyi"], output="out2.pyi")
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          {"output"}, input_options, self.output_options).process()

  def test_dependency(self):
    input_options = types.SimpleNamespace(output="test.pyi", check=None)
    config.Postprocessor(
        {"output", "check"}, input_options, self.output_options).process()
    self.assertEqual(self.output_options.output, "test.pyi")
    self.assertIs(self.output_options.check, False)

  def test_subset(self):
    python_version = sys.version_info[:2]
    input_options = types.SimpleNamespace(
        pythonpath=".", python_version=utils.format_version(python_version))
    config.Postprocessor(
        {"python_version"}, input_options, self.output_options).process()
    with self.assertRaises(AttributeError):
      _ = self.output_options.pythonpath  # not processed
    self.assertTupleEqual(self.output_options.python_version, python_version)

  def test_error(self):
    input_options = types.SimpleNamespace(check=True, output="test.pyi")
    with self.assertRaises(config.PostprocessingError):
      config.Postprocessor(
          {"check", "output"}, input_options, self.output_options).process()

  def test_inplace(self):
    python_version = sys.version_info[:2]
    input_options = types.SimpleNamespace(
        disable="import-error,attribute-error",
        python_version=utils.format_version(python_version))
    config.Postprocessor(
        {"disable", "python_version"}, input_options).process()
    self.assertSequenceEqual(
        input_options.disable, ["import-error", "attribute-error"])
    self.assertTupleEqual(input_options.python_version, python_version)

  def test_typeshed_default(self):
    input_options = types.SimpleNamespace(
        typeshed=None, precompiled_builtins=None)
    config.Postprocessor({"typeshed", "precompiled_builtins"}, input_options,
                         self.output_options).process()
    # We only care that `None` was replaced.
    self.assertIsNotNone(self.output_options.typeshed)

  def test_typeshed_with_precompiled_builtins(self):
    input_options = types.SimpleNamespace(
        typeshed=None, precompiled_builtins="builtins")
    config.Postprocessor({"typeshed", "precompiled_builtins"}, input_options,
                         self.output_options).process()
    self.assertIs(self.output_options.typeshed, False)

  def test_typeshed(self):
    input_options = types.SimpleNamespace(
        typeshed=False, precompiled_builtins=None)
    config.Postprocessor({"typeshed", "precompiled_builtins"}, input_options,
                         self.output_options).process()
    self.assertIs(self.output_options.typeshed, False)

  def test_enable_only(self):
    input_options = types.SimpleNamespace(
        disable=None,
        enable_only="import-error,attribute-error")
    config.Postprocessor({"disable", "enable_only"}, input_options,
                         self.output_options).process()
    self.assertIn("python-compiler-error", self.output_options.disable)
    self.assertNotIn("import-error", self.output_options.disable)
    self.assertNotIn("attribute-error", self.output_options.disable)

  def test_disable_and_enable_only(self):
    input_options = types.SimpleNamespace(
        disable="import-error,attribute-error",
        enable_only="bad-slots,bad-unpacking")
    with self.assertRaises(config.PostprocessingError) as _:
      config.Postprocessor({"disable", "enable_only"}, input_options,
                           self.output_options).process()

  def test_python_version_default(self):
    input_options = types.SimpleNamespace(python_version=None)
    config.Postprocessor({"python_version"}, input_options,
                         self.output_options).process()
    self.assertEqual(self.output_options.python_version,
                     (sys.version_info.major, sys.version_info.minor))

  def test_unknown_option(self):
    with self.assertRaises(ValueError):
      config.Options.create(something_something_something_shrubbery=0)

  def test_open_function(self):
    options = config.Options.create()
    self.assertIs(options.open_function, open)

  def test_custom_open_function(self):
    open_function = lambda _: None
    options = config.Options.create(open_function=open_function)
    self.assertIs(options.open_function, open_function)


if __name__ == "__main__":
  unittest.main()
