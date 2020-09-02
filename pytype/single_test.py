"""Integration test for pytype."""

import csv
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

from pytype import config
from pytype import single
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import typeshed
from pytype.pytd.parse import builtins
from pytype.tests import test_base
import unittest


class PytypeTest(test_base.UnitTest):
  """Integration test for pytype."""

  DEFAULT_PYI = builtins.DEFAULT_SRC
  INCLUDE = object()

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls.pytype_dir = os.path.dirname(os.path.dirname(parser.__file__))

  def setUp(self):
    super().setUp()
    self._reset_pytype_args()
    self.tmp_dir = tempfile.mkdtemp()
    self.errors_csv = os.path.join(self.tmp_dir, "errors.csv")

  def tearDown(self):
    super().tearDown()
    shutil.rmtree(self.tmp_dir)

  def _reset_pytype_args(self):
    self.pytype_args = {
        "--python_version": utils.format_version(self.python_version),
        "--verbosity": 1
    }

  def _data_path(self, filename):
    if os.path.dirname(filename) == self.tmp_dir:
      return filename
    return os.path.join(self.pytype_dir, "test_data/", filename)

  def _tmp_path(self, filename):
    return os.path.join(self.tmp_dir, filename)

  def _make_py_file(self, contents):
    if utils.USE_ANNOTATIONS_BACKPORT:
      contents = test_base.WithAnnotationsImport(contents)
    return self._make_file(contents, extension=".py")

  def _make_file(self, contents, extension):
    contents = textwrap.dedent(contents)
    path = self._tmp_path(
        hashlib.md5(contents.encode("utf-8")).hexdigest() + extension)
    with open(path, "w") as f:
      print(contents, file=f)
    return path

  def _run_pytype(self, pytype_args_dict):
    """A single command-line call to the pytype binary.

    Typically you'll want to use _CheckTypesAndErrors or
    _InferTypesAndCheckErrors, which will set up the command-line arguments
    properly and check that the errors file is in the right state after the
    call. (The errors check is bundled in to avoid the user forgetting to call
    assertHasErrors() with no arguments when expecting no errors.)

    Args:
      pytype_args_dict: A dictionary of the arguments to pass to pytype, minus
       the binary name. For example, to run
          pytype simple.py --output=-
       the arguments should be {"simple.py": self.INCLUDE, "--output": "-"}
    """
    pytype_exe = os.path.join(self.pytype_dir, "pytype")
    pytype_args = [pytype_exe]
    for arg, value in pytype_args_dict.items():
      if value is not self.INCLUDE:
        arg += "=" + str(value)
      pytype_args.append(arg)
    p = subprocess.Popen(
        pytype_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    self.stdout, self.stderr = (s.decode("utf-8") for s in p.communicate())
    self.returncode = p.returncode

  def _parse_string(self, string):
    """A wrapper for parser.parse_string that inserts the python version."""
    return parser.parse_string(string, python_version=self.python_version)

  def _generate_builtins_twice(self, python_version):
    os.environ["PYTHONHASHSEED"] = "0"
    f1 = self._tmp_path("builtins1.pickle")
    f2 = self._tmp_path("builtins2.pickle")
    for f in (f1, f2):
      self.pytype_args["--generate-builtins"] = f
      self.pytype_args["--python_version"] = python_version
      self._run_pytype(self.pytype_args)
    return f1, f2

  def assertBuiltinsPickleEqual(self, f1, f2):
    with open(f1, "rb") as pickle1, open(f2, "rb") as pickle2:
      if pickle1.read() == pickle2.read():
        return
    out1 = pytd_utils.LoadPickle(f1, compress=True)
    out2 = pytd_utils.LoadPickle(f2, compress=True)
    raise AssertionError("\n".join(pytd_utils.DiffNamedPickles(out1, out2)))

  def assertOutputStateMatches(self, **has_output):
    """Check that the output state matches expectations.

    If, for example, you expect the program to print something to stdout and
    nothing to stderr before exiting with an error code, you would write
    assertOutputStateMatches(stdout=True, stderr=False, returncode=True).

    Args:
      **has_output: Whether each output type should have output.
    """
    output_types = {"stdout", "stderr", "returncode"}
    assert len(output_types) == len(has_output)
    for output_type in output_types:
      output_value = getattr(self, output_type)
      if has_output[output_type]:
        self.assertTrue(output_value, output_type + " unexpectedly empty")
      else:
        value = str(output_value)
        if len(value) > 50:
          value = value[:47] + "..."
        self.assertFalse(
            output_value, "Unexpected output to %s: %r" % (output_type, value))

  def assertHasErrors(self, *expected_errors):
    with open(self.errors_csv, "r") as f:
      errors = list(csv.reader(f, delimiter=","))
    num, expected_num = len(errors), len(expected_errors)
    try:
      self.assertEqual(num, expected_num,
                       "Expected %d errors, got %d" % (expected_num, num))
      for error, expected_error in zip(errors, expected_errors):
        self.assertEqual(expected_error, error[2],
                         "Expected %r, got %r" % (expected_error, error[2]))
    except:
      print("\n".join(" | ".join(error) for error in errors), file=sys.stderr)
      raise

  def _setup_checking(self, filename):
    self.pytype_args[self._data_path(filename)] = self.INCLUDE
    self.pytype_args["--check"] = self.INCLUDE

  def _check_types_and_errors(self, filename, expected_errors):
    self._setup_checking(filename)
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertHasErrors(*expected_errors)

  def _infer_types_and_check_errors(self, filename, expected_errors):
    self.pytype_args[self._data_path(filename)] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertHasErrors(*expected_errors)

  def assertInferredPyiEquals(self, expected_pyi=None, filename=None):
    assert bool(expected_pyi) != bool(filename)
    if filename:
      with open(self._data_path(filename), "r") as f:
        expected_pyi = f.read()
    message = ("\n==Expected pyi==\n" + expected_pyi +
               "\n==Actual pyi==\n" + self.stdout)
    self.assertTrue(pytd_utils.ASTeq(self._parse_string(self.stdout),
                                     self._parse_string(expected_pyi)), message)

  def generate_pickled_simple_file(self, pickle_name, verify_pickle=True):
    pickled_location = os.path.join(self.tmp_dir, pickle_name)
    self.pytype_args["--pythonpath"] = self.tmp_dir
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args["--module-name"] = "simple"
    if verify_pickle:
      self.pytype_args["--verify-pickle"] = self.INCLUDE
    self.pytype_args["--output"] = pickled_location
    self.pytype_args[self._data_path("simple.py")] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=0)
    self.assertTrue(os.path.exists(pickled_location))
    return pickled_location

  def test_run_pytype(self):
    """Basic unit test (smoke test) for _run_pytype."""
    # Note: all other tests in this file are integration tests.
    infile = self._tmp_path("input")
    outfile = self._tmp_path("output")
    with open(infile, "w") as f:
      f.write("def f(x): pass")
    options = config.Options.create(infile, output=outfile)
    single._run_pytype(options)
    self.assertTrue(os.path.isfile(outfile))

  def test_pickled_file_stableness(self):
    # Tests that the pickled format is stable under a constant PYTHONHASHSEED.
    l_1 = self.generate_pickled_simple_file("simple1.pickled")
    l_2 = self.generate_pickled_simple_file("simple2.pickled")
    with open(l_1, "rb") as f_1:
      with open(l_2, "rb") as f_2:
        self.assertEqual(f_1.read(), f_2.read())

  def test_generate_pickled_ast(self):
    self.generate_pickled_simple_file("simple.pickled", verify_pickle=True)

  def test_generate_unverified_pickled_ast(self):
    self.generate_pickled_simple_file("simple.pickled", verify_pickle=False)

  def test_pickle_no_output(self):
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args[self._data_path("simple.py")] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_pickle_bad_output(self):
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args["--output"] = os.path.join(self.tmp_dir, "simple.pyi")
    self.pytype_args[self._data_path("simple.py")] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_bad_verify_pickle(self):
    self.pytype_args["--verify-pickle"] = self.INCLUDE
    self.pytype_args[self._data_path("simple.py")] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_nonexistent_option(self):
    self.pytype_args["--rumpelstiltskin"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_cfg_typegraph_conflict(self):
    self._setup_checking("simple.py")
    output_path = self._tmp_path("simple.svg")
    self.pytype_args["--output-cfg"] = output_path
    self.pytype_args["--output-typegraph"] = output_path
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_check_infer_conflict(self):
    self.pytype_args["--check"] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_check_infer_conflict2(self):
    self.pytype_args["--check"] = self.INCLUDE
    self.pytype_args["input.py:output.pyi"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_input_output_pair(self):
    self.pytype_args[self._data_path("simple.py") +":-"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertInferredPyiEquals(filename="simple.pyi")

  def test_multiple_output(self):
    self.pytype_args["input.py:output1.pyi"] = self.INCLUDE
    self.pytype_args["--output"] = "output2.pyi"
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_generate_builtins_input_conflict(self):
    self.pytype_args["--generate-builtins"] = "builtins.py"
    self.pytype_args["input.py"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_generate_builtins_pythonpath_conflict(self):
    self.pytype_args["--generate-builtins"] = "builtins.py"
    self.pytype_args["--pythonpath"] = "foo:bar"
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_generate_builtins_py2(self):
    self.pytype_args["--generate-builtins"] = self._tmp_path("builtins.py")
    self.pytype_args["--python_version"] = "2.7"
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_generate_builtins_py3(self):
    self.pytype_args["--generate-builtins"] = self._tmp_path("builtins.py")
    self.pytype_args["--python_version"] = utils.format_version(
        utils.full_version_from_major(3))
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_missing_input(self):
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_multiple_input(self):
    self.pytype_args["input1.py"] = self.INCLUDE
    self.pytype_args["input2.py"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_bad_input_format(self):
    self.pytype_args["input.py:output.pyi:rumpelstiltskin"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_pytype_errors(self):
    self._setup_checking("bad.py")
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)
    self.assertIn("[unsupported-operands]", self.stderr)
    self.assertIn("[name-error]", self.stderr)

  def test_pytype_errors_csv(self):
    self._setup_checking("bad.py")
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertHasErrors("unsupported-operands", "name-error")

  def test_pytype_errors_no_report(self):
    self._setup_checking("bad.py")
    self.pytype_args["--no-report-errors"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_pytype_return_success(self):
    self._setup_checking("bad.py")
    self.pytype_args["--return-success"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=False)
    self.assertIn("[unsupported-operands]", self.stderr)
    self.assertIn("[name-error]", self.stderr)

  def test_compiler_error(self):
    self._check_types_and_errors("syntax.py", ["python-compiler-error"])

  def test_multi_line_string_token_error(self):
    self._check_types_and_errors("tokenerror1.py", ["python-compiler-error"])

  def test_multi_line_statement_token_error(self):
    self._check_types_and_errors("tokenerror2.py", ["python-compiler-error"])

  def test_complex(self):
    self._check_types_and_errors("complex.py", [])

  def test_check(self):
    self._check_types_and_errors("simple.py", [])

  def test_return_type(self):
    self._check_types_and_errors(self._make_py_file("""
      def f() -> int:
        return "foo"
    """), ["bad-return-type"])

  def test_usage_error(self):
    self._setup_checking(self._make_py_file("""
      def f():
        pass
    """))
    # Set up a python version mismatch
    self.pytype_args["--python_version"] = "3.5"
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def test_skip_file(self):
    filename = self._make_py_file("""
        # pytype: skip-file
    """)
    self.pytype_args[self._data_path(filename)] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertInferredPyiEquals(expected_pyi=self.DEFAULT_PYI)

  def test_infer(self):
    self._infer_types_and_check_errors("simple.py", [])
    self.assertInferredPyiEquals(filename="simple.pyi")

  def test_infer_pytype_errors(self):
    self._infer_types_and_check_errors(
        "bad.py", ["unsupported-operands", "name-error"])
    self.assertInferredPyiEquals(filename="bad.pyi")

  def test_infer_compiler_error(self):
    self._infer_types_and_check_errors("syntax.py", ["python-compiler-error"])
    self.assertInferredPyiEquals(expected_pyi=self.DEFAULT_PYI)

  def test_infer_complex(self):
    self._infer_types_and_check_errors("complex.py", [])
    self.assertInferredPyiEquals(filename="complex.pyi")

  def test_check_main(self):
    self._setup_checking(self._make_py_file("""
      def f():
        name_error
      def g():
        "".foobar
      g()
    """))
    self.pytype_args["--main"] = self.INCLUDE
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._run_pytype(self.pytype_args)
    self.assertHasErrors("attribute-error")

  def test_infer_to_file(self):
    self.pytype_args[self._data_path("simple.py")] = self.INCLUDE
    pyi_file = self._tmp_path("simple.pyi")
    self.pytype_args["--output"] = pyi_file
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    with open(pyi_file, "r") as f:
      pyi = f.read()
    with open(self._data_path("simple.pyi"), "r") as f:
      expected_pyi = f.read()
    self.assertTrue(pytd_utils.ASTeq(self._parse_string(pyi),
                                     self._parse_string(expected_pyi)))

  def test_parse_pyi(self):
    self.pytype_args[self._data_path("complex.pyi")] = self.INCLUDE
    self.pytype_args["--parse-pyi"] = self.INCLUDE
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_pytree(self):
    """Test pytype on a real-world program."""
    self.pytype_args["--quick"] = self.INCLUDE
    self._infer_types_and_check_errors("pytree.py", [
        "import-error", "import-error", "attribute-error", "attribute-error",
        "attribute-error", "name-error"])
    ast = self._parse_string(self.stdout)
    self.assertListEqual(["convert", "generate_matches", "type_repr"],
                         [f.name for f in ast.functions])
    self.assertListEqual(
        ["Base", "BasePattern", "Leaf", "LeafPattern", "NegatedPattern", "Node",
         "NodePattern", "WildcardPattern"],
        [c.name for c in ast.classes])

  def test_no_analyze_annotated(self):
    filename = self._make_py_file("""
      def f() -> str:
        return 42
    """)
    self._infer_types_and_check_errors(self._data_path(filename), [])

  def test_analyze_annotated(self):
    filename = self._make_py_file("""
      def f() -> str:
        return 42
    """)
    self.pytype_args["--analyze-annotated"] = self.INCLUDE
    self._infer_types_and_check_errors(self._data_path(filename),
                                       ["bad-return-type"])

  def test_generate_and_use_builtins(self):
    """Test for --generate-builtins."""
    filename = self._tmp_path("builtins.pickle")
    # Generate builtins pickle
    self.pytype_args["--generate-builtins"] = filename
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertTrue(os.path.isfile(filename))
    src = self._make_py_file("""
      import __future__
      import sys
      import collections
      import typing
    """)
    # Use builtins pickle
    self._reset_pytype_args()
    self._setup_checking(src)
    self.pytype_args["--precompiled-builtins"] = filename
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_use_builtins_and_import_map(self):
    """Test for --generate-builtins."""
    filename = self._tmp_path("builtins.pickle")
    # Generate builtins pickle
    self.pytype_args["--generate-builtins"] = filename
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertTrue(os.path.isfile(filename))
    # input files
    canary = "import pytypecanary" if typeshed.Typeshed.MISSING_FILE else ""
    src = self._make_py_file("""
      import __future__
      import asyncio
      import sys
      import collections
      import typing
      import foo
      import csv
      import ctypes
      import xml.etree.ElementTree as ElementTree
      %s
      x = foo.x
      y = csv.writer
      z = asyncio.coroutine
    """ % canary)
    pyi = self._make_file("""
      import datetime
      x = ...  # type: datetime.tzinfo
    """, extension=".pyi")
    # Use builtins pickle with an imports map
    self._reset_pytype_args()
    self._setup_checking(src)
    self.pytype_args["--precompiled-builtins"] = filename
    self.pytype_args["--imports_info"] = self._make_file("""
      typing /dev/null
      foo %s
    """ % pyi, extension="")
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def test_builtins_determinism2(self):
    f1, f2 = self._generate_builtins_twice("2.7")
    self.assertBuiltinsPickleEqual(f1, f2)

  def test_builtins_determinism3(self):
    f1, f2 = self._generate_builtins_twice(
        utils.format_version(utils.full_version_from_major(3)))
    self.assertBuiltinsPickleEqual(f1, f2)

  def test_timeout(self):
    # Note: At the time of this writing, pickling builtins takes well over one
    # second (~10s). If it ever was to get faster, this test would become flaky.
    self.pytype_args["--timeout"] = 1
    self.pytype_args["--generate-builtins"] = self._tmp_path("builtins.pickle")
    self._run_pytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=True)


def main():
  unittest.main()


if __name__ == "__main__":
  main()
