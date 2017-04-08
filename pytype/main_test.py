"""Integration test for pytype."""

import csv
import hashlib
import os
import shutil
import subprocess
import textwrap

from pytype import utils
from pytype.pyi import parser
from pytype.pytd.parse import builtins
from google.apputils import basetest
import unittest


class PytypeTest(unittest.TestCase):
  """Integration test for pytype."""


  DEFAULT_PYI = builtins.DEFAULT_SRC
  INCLUDE = object()

  @classmethod
  def setUpClass(cls):
    cls.pytype_dir = os.path.dirname(os.path.dirname(parser.__file__))
    cls.tmp_dir = basetest._GetDefaultTestTmpdir()
    cls.errors_csv = os.path.join(cls.tmp_dir, "errors.csv")

  def setUp(self):
    self._ResetPytypeArgs()
    # Remove the errors file between runs so that assertHasErrors reliably
    # fails if pytype hasn't been executed with --output-errors-csv.
    if os.path.exists(self.errors_csv):
      os.remove(self.errors_csv)
    self.tmp_files = set()

  def tearDown(self):
    for f in self.tmp_files:
      os.remove(f)

  def _ResetPytypeArgs(self):
    self.pytype_args = {"--python_exe": self.PYTHON_EXE,
                        "--verbosity": 1}

  def _DataPath(self, filename):
    if os.path.dirname(filename) == self.tmp_dir:
      return filename
    return os.path.join(self.pytype_dir, "test_data/", filename)

  def _TmpPath(self, filename):
    path = os.path.join(self.tmp_dir, filename)
    self.tmp_files.add(path)
    return path

  def _MakeFile(self, contents):
    contents = textwrap.dedent(contents)
    path = self._TmpPath(hashlib.md5(contents).hexdigest() + ".py")
    with open(path, "w") as f:
      print >>f, contents
    self.tmp_files.add(path)
    return path

  def _RunPytype(self, pytype_args_dict):
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
    self.stdout, self.stderr = p.communicate()
    self.returncode = p.returncode

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
        self.assertTrue(output_value)
      else:
        self.assertFalse(output_value)

  def assertHasErrors(self, *expected_errors):
    with open(self.errors_csv, "r") as f:
      errors = list(csv.reader(f, delimiter=","))
    self.assertEquals(len(errors), len(expected_errors))
    for error, expected_error in zip(errors, expected_errors):
      self.assertIn(expected_error, error)

  def _SetUpChecking(self, filename):
    self.pytype_args[self._DataPath(filename)] = self.INCLUDE
    self.pytype_args["--check"] = self.INCLUDE

  def _CheckTypesAndErrors(self, filename, expected_errors):
    self._SetUpChecking(filename)
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertHasErrors(*expected_errors)

  def _InferTypesAndCheckErrors(self, filename, expected_errors):
    self.pytype_args[self._DataPath(filename)] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertHasErrors(*expected_errors)

  def assertInferredPyiEquals(self, expected_pyi=None, filename=None):
    assert bool(expected_pyi) != bool(filename)
    if filename:
      with open(self._DataPath(filename), "r") as f:
        expected_pyi = f.read()
    self.assertTrue(parser.parse_string(self.stdout).ASTeq(
        parser.parse_string(expected_pyi)))

  def testPickledAstLocationWithoutModuleName(self):
    self.pytype_args[self._DataPath("simple.pyi")] = self.INCLUDE
    pickled_location = "/unused location as this tests an error."
    self.pytype_args["--read-pyi-save-pickle"] = pickled_location
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=1)

  def testPickledAstLocation(self):
    with utils.Tempdir() as d:
      simple_pyi_path = os.path.join(d.path, "simple.pyi")
      shutil.copyfile(self._DataPath("simple.pyi"), simple_pyi_path)

      pickled_location = os.path.join(d.path, "simple.pyi.pickled")
      self.pytype_args[simple_pyi_path] = self.INCLUDE
      self.pytype_args["--pythonpath"] = d.path
      self.pytype_args["--read-pyi-save-pickle"] = pickled_location
      self.pytype_args["--module-name"] = "simple"
      self._RunPytype(self.pytype_args)
      self.assertTrue(os.path.exists(pickled_location))
      self.assertOutputStateMatches(stdout=False, stderr=False, returncode=0)

  def testUsePickledFiles(self):
    with utils.Tempdir() as d:
      # Create the pickled dependency
      simple_pyi_path = os.path.join(d.path, "simple.pyi")
      shutil.copyfile(self._DataPath("simple.pyi"), simple_pyi_path)

      pickled_location = os.path.join(d.path, "simple.pyi.pickled")
      self.pytype_args[simple_pyi_path] = self.INCLUDE
      self.pytype_args["--pythonpath"] = d.path
      self.pytype_args["--read-pyi-save-pickle"] = pickled_location
      self.pytype_args["--module-name"] = "simple"
      self._RunPytype(self.pytype_args)
      self.assertTrue(os.path.exists(pickled_location))
      self.assertOutputStateMatches(stdout=False, stderr=False, returncode=0)
      self._ResetPytypeArgs()

      # Get the importing file to pythonpath.
      imports_py_path = os.path.join(d.path, "imports.py")
      shutil.copyfile(self._DataPath("imports.py"), imports_py_path)

      self.pytype_args["--use-pickled-files"] = self.INCLUDE
      self.pytype_args["--pythonpath"] = d.path

      self._InferTypesAndCheckErrors(imports_py_path, [])

  def testBadOption(self):
    self.pytype_args["--rumpelstiltskin"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testPytypeErrors(self):
    self._SetUpChecking("bad.py")
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)
    self.assertIn("[wrong-arg-types]", self.stderr)
    self.assertIn("[name-error]", self.stderr)

  def testPytypeErrorsCsv(self):
    self._SetUpChecking("bad.py")
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertHasErrors("wrong-arg-types", "name-error")

  def testPytypeErrorsNoReport(self):
    self._SetUpChecking("bad.py")
    self.pytype_args["--no-report-errors"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testCompilerError(self):
    self._CheckTypesAndErrors("syntax.py", ["python-compiler-error"])

  def testComplex(self):
    self._CheckTypesAndErrors("complex.py", [])

  def testCheck(self):
    self._CheckTypesAndErrors("simple.py", [])

  def testReturnType(self):
    self._CheckTypesAndErrors(self._MakeFile("""\
      from __future__ import google_type_annotations
      def f() -> int:
        return "foo"
    """), ["bad-return-type"])

  def testInfer(self):
    self._InferTypesAndCheckErrors("simple.py", [])
    self.assertInferredPyiEquals(filename="simple.pyi")

  def testInferPytypeErrors(self):
    self._InferTypesAndCheckErrors(
        "bad.py", ["wrong-arg-types", "name-error"])
    self.assertInferredPyiEquals(filename="bad.pyi")

  def testInferCompilerError(self):
    self._InferTypesAndCheckErrors("syntax.py", ["python-compiler-error"])
    self.assertInferredPyiEquals(expected_pyi=self.DEFAULT_PYI)

  def testInferComplex(self):
    self._InferTypesAndCheckErrors("complex.py", [])
    self.assertInferredPyiEquals(filename="complex.pyi")

  def testCheckMain(self):
    self._SetUpChecking(self._MakeFile("""\
      def f():
        name_error
      def g():
        "".foobar
      g()
    """))
    self.pytype_args["--main"] = self.INCLUDE
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertHasErrors("attribute-error")

  def testInferToFile(self):
    self.pytype_args[self._DataPath("simple.py")] = self.INCLUDE
    pyi_file = self._TmpPath("simple.pyi")
    self.pytype_args["--output"] = pyi_file
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    with open(pyi_file, "r") as f:
      pyi = f.read()
    with open(self._DataPath("simple.pyi"), "r") as f:
      expected_pyi = f.read()
    self.assertTrue(parser.parse_string(pyi).ASTeq(
        parser.parse_string(expected_pyi)))

  def testPytree(self):
    """Test pytype on a real-world program."""
    self.pytype_args["--quick"] = self.INCLUDE
    self._InferTypesAndCheckErrors("pytree.py", [
        "import-error", "import-error", "attribute-error",
        "attribute-error", "name-error"])
    ast = parser.parse_string(self.stdout)
    self.assertListEqual(["convert", "generate_matches", "type_repr"],
                         [f.name for f in ast.functions])
    self.assertListEqual(
        ["Base", "BasePattern", "Leaf", "LeafPattern", "NegatedPattern", "Node",
         "NodePattern", "WildcardPattern"],
        [c.name for c in ast.classes])


def main():
  unittest.main()


if __name__ == "__main__":
  main()
