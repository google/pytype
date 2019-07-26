"""Integration test for pytype."""
from __future__ import print_function

import csv
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

from pytype import config
from pytype import main as main_module
from pytype import utils
from pytype.pyi import parser
from pytype.pytd import pytd_utils
from pytype.pytd import typeshed
from pytype.pytd.parse import builtins
from pytype.tests import test_base
import unittest


class PytypeTest(unittest.TestCase):
  """Integration test for pytype."""

  PYTHON_VERSION = (2, 7)

  DEFAULT_PYI = builtins.DEFAULT_SRC
  INCLUDE = object()

  @classmethod
  def setUpClass(cls):
    super(PytypeTest, cls).setUpClass()
    cls.pytype_dir = os.path.dirname(os.path.dirname(parser.__file__))

  def setUp(self):
    super(PytypeTest, self).setUp()
    self._ResetPytypeArgs()
    self.tmp_dir = tempfile.mkdtemp()
    self.errors_csv = os.path.join(self.tmp_dir, "errors.csv")

  def tearDown(self):
    super(PytypeTest, self).tearDown()
    shutil.rmtree(self.tmp_dir)

  def _ResetPytypeArgs(self):
    self.pytype_args = {
        "--python_version": utils.format_version(self.PYTHON_VERSION),
        "--verbosity": 1
    }

  def _DataPath(self, filename):
    if os.path.dirname(filename) == self.tmp_dir:
      return filename
    return os.path.join(self.pytype_dir, "test_data/", filename)

  def _TmpPath(self, filename):
    return os.path.join(self.tmp_dir, filename)

  def _MakePyFile(self, contents):
    if utils.USE_ANNOTATIONS_BACKPORT:
      contents = test_base.WithAnnotationsImport(contents)
    return self._MakeFile(contents, extension=".py")

  def _MakeFile(self, contents, extension):
    contents = textwrap.dedent(contents)
    path = self._TmpPath(
        hashlib.md5(contents.encode("utf-8")).hexdigest() + extension)
    with open(path, "w") as f:
      print(contents, file=f)
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
    self.stdout, self.stderr = (s.decode("utf-8") for s in p.communicate())
    self.returncode = p.returncode

  def _ParseString(self, string):
    """A wrapper for parser.parse_string that inserts the python version."""
    return parser.parse_string(string, python_version=self.PYTHON_VERSION)

  def _GenerateBuiltinsTwice(self, python_version):
    os.environ["PYTHONHASHSEED"] = "0"
    f1 = self._TmpPath("builtins1.pickle")
    f2 = self._TmpPath("builtins2.pickle")
    for f in (f1, f2):
      self.pytype_args["--generate-builtins"] = f
      self.pytype_args["--python_version"] = python_version
      self._RunPytype(self.pytype_args)
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
    message = ("\n==Expected pyi==\n" + expected_pyi +
               "\n==Actual pyi==\n" + self.stdout)
    self.assertTrue(self._ParseString(self.stdout).ASTeq(
        self._ParseString(expected_pyi)), message)

  def GeneratePickledSimpleFile(self, pickle_name, verify_pickle=True):
    pickled_location = os.path.join(self.tmp_dir, pickle_name)
    self.pytype_args["--pythonpath"] = self.tmp_dir
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args["--module-name"] = "simple"
    if verify_pickle:
      self.pytype_args["--verify-pickle"] = self.INCLUDE
    self.pytype_args["--output"] = pickled_location
    self.pytype_args[self._DataPath("simple.py")] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=0)
    self.assertTrue(os.path.exists(pickled_location))
    return pickled_location

  def testPickledFileStableness(self):
    # Tests that the pickled format is stable under a constant PYTHONHASHSEED.
    l_1 = self.GeneratePickledSimpleFile("simple1.pickled")
    l_2 = self.GeneratePickledSimpleFile("simple2.pickled")
    with open(l_1, "rb") as f_1:
      with open(l_2, "rb") as f_2:
        self.assertEqual(f_1.read(), f_2.read())

  def testGeneratePickledAst(self):
    self.GeneratePickledSimpleFile("simple.pickled", verify_pickle=True)

  def testGenerateUnverifiedPickledAst(self):
    self.GeneratePickledSimpleFile("simple.pickled", verify_pickle=False)

  def testPickleNoOutput(self):
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args[self._DataPath("simple.py")] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testPickleBadOutput(self):
    self.pytype_args["--pickle-output"] = self.INCLUDE
    self.pytype_args["--output"] = os.path.join(self.tmp_dir, "simple.pyi")
    self.pytype_args[self._DataPath("simple.py")] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testBadVerifyPickle(self):
    self.pytype_args["--verify-pickle"] = self.INCLUDE
    self.pytype_args[self._DataPath("simple.py")] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testNonexistentOption(self):
    self.pytype_args["--rumpelstiltskin"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testCfgTypegraphConflict(self):
    self._SetUpChecking("simple.py")
    output_path = self._TmpPath("simple.svg")
    self.pytype_args["--output-cfg"] = output_path
    self.pytype_args["--output-typegraph"] = output_path
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testCheckInferConflict(self):
    self.pytype_args["--check"] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testCheckInferConflict2(self):
    self.pytype_args["--check"] = self.INCLUDE
    self.pytype_args["input.py:output.pyi"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testInputOutputPair(self):
    self.pytype_args[self._DataPath("simple.py") +":-"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertInferredPyiEquals(filename="simple.pyi")

  def testMultipleOutput(self):
    self.pytype_args["input.py:output1.pyi"] = self.INCLUDE
    self.pytype_args["--output"] = "output2.pyi"
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testGenerateBuiltinsInputConflict(self):
    self.pytype_args["--generate-builtins"] = "builtins.py"
    self.pytype_args["input.py"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testGenerateBuiltinsPythonpathConflict(self):
    self.pytype_args["--generate-builtins"] = "builtins.py"
    self.pytype_args["--pythonpath"] = "foo:bar"
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testGenerateBuiltinsPy2(self):
    self.pytype_args["--generate-builtins"] = self._TmpPath("builtins.py")
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testGenerateBuiltinsPy3(self):
    self.pytype_args["--generate-builtins"] = self._TmpPath("builtins.py")
    self.pytype_args["--python_version"] = "3.6"
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testMissingInput(self):
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testMultipleInput(self):
    self.pytype_args["input1.py"] = self.INCLUDE
    self.pytype_args["input2.py"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testBadInputFormat(self):
    self.pytype_args["input.py:output.pyi:rumpelstiltskin"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testPytypeErrors(self):
    self._SetUpChecking("bad.py")
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)
    self.assertIn("[unsupported-operands]", self.stderr)
    self.assertIn("[name-error]", self.stderr)

  def testPytypeErrorsCsv(self):
    self._SetUpChecking("bad.py")
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertHasErrors("unsupported-operands", "name-error")

  def testPytypeErrorsNoReport(self):
    self._SetUpChecking("bad.py")
    self.pytype_args["--no-report-errors"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testPytypeReturnSuccess(self):
    self._SetUpChecking("bad.py")
    self.pytype_args["--return-success"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=False)
    self.assertIn("[unsupported-operands]", self.stderr)
    self.assertIn("[name-error]", self.stderr)

  def testCompilerError(self):
    self._CheckTypesAndErrors("syntax.py", ["python-compiler-error"])

  def testMultiLineStringTokenError(self):
    self._CheckTypesAndErrors("tokenerror1.py", ["python-compiler-error"])

  def testMultiLineStatementTokenError(self):
    self._CheckTypesAndErrors("tokenerror2.py", ["python-compiler-error"])

  def testComplex(self):
    self._CheckTypesAndErrors("complex.py", [])

  def testCheck(self):
    self._CheckTypesAndErrors("simple.py", [])

  def testReturnType(self):
    self._CheckTypesAndErrors(self._MakePyFile("""\
      def f() -> int:
        return "foo"
    """), ["bad-return-type"])

  def testUsageError(self):
    self._SetUpChecking(self._MakePyFile("""\
      def f():
        pass
    """))
    # Set up a python version mismatch
    self.pytype_args["--python_version"] = "3.4"
    self.pytype_args["--output-errors-csv"] = self.errors_csv
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=True, returncode=True)

  def testSkipFile(self):
    filename = self._MakePyFile("""\
        # pytype: skip-file
    """)
    self.pytype_args[self._DataPath(filename)] = self.INCLUDE
    self.pytype_args["--output"] = "-"
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=True, stderr=False, returncode=False)
    self.assertInferredPyiEquals(expected_pyi=self.DEFAULT_PYI)

  def testInfer(self):
    self._InferTypesAndCheckErrors("simple.py", [])
    self.assertInferredPyiEquals(filename="simple.pyi")

  def testInferPytypeErrors(self):
    self._InferTypesAndCheckErrors(
        "bad.py", ["unsupported-operands", "name-error"])
    self.assertInferredPyiEquals(filename="bad.pyi")

  def testInferCompilerError(self):
    self._InferTypesAndCheckErrors("syntax.py", ["python-compiler-error"])
    self.assertInferredPyiEquals(expected_pyi=self.DEFAULT_PYI)

  def testInferComplex(self):
    self._InferTypesAndCheckErrors("complex.py", [])
    self.assertInferredPyiEquals(filename="complex.pyi")

  def testCheckMain(self):
    self._SetUpChecking(self._MakePyFile("""\
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
    self.assertTrue(self._ParseString(pyi).ASTeq(
        self._ParseString(expected_pyi)))

  def testParsePyi(self):
    self.pytype_args[self._DataPath("complex.pyi")] = self.INCLUDE
    self.pytype_args["--parse-pyi"] = self.INCLUDE
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testPytree(self):
    """Test pytype on a real-world program."""
    self.pytype_args["--quick"] = self.INCLUDE
    self._InferTypesAndCheckErrors("pytree.py", [
        "import-error", "import-error", "attribute-error", "attribute-error",
        "attribute-error", "name-error"])
    ast = self._ParseString(self.stdout)
    self.assertListEqual(["convert", "generate_matches", "type_repr"],
                         [f.name for f in ast.functions])
    self.assertListEqual(
        ["Base", "BasePattern", "Leaf", "LeafPattern", "NegatedPattern", "Node",
         "NodePattern", "WildcardPattern"],
        [c.name for c in ast.classes])

  def testNoAnalyzeAnnotated(self):
    filename = self._MakePyFile("""\
      def f() -> str:
        return 42
    """)
    self._InferTypesAndCheckErrors(self._DataPath(filename), [])

  def testAnalyzeAnnotated(self):
    filename = self._MakePyFile("""\
      def f() -> str:
        return 42
    """)
    self.pytype_args["--analyze-annotated"] = self.INCLUDE
    self._InferTypesAndCheckErrors(self._DataPath(filename),
                                   ["bad-return-type"])

  def testRunPytype(self):
    """Basic unit test (smoke test) for _run_pytype."""
    # TODO(kramm): This is a unit test, whereas all other tests in this file
    # are integration tests. Move this somewhere else?
    infile = self._TmpPath("input")
    outfile = self._TmpPath("output")
    with open(infile, "w") as f:
      f.write("def f(x): pass")
    options = config.Options.create(infile, output=outfile)
    main_module._run_pytype(options)
    self.assertTrue(os.path.isfile(outfile))

  def testGenerateAndUseBuiltins(self):
    """Test for --generate-builtins."""
    filename = self._TmpPath("builtins.pickle")
    # Generate builtins pickle
    self.pytype_args["--generate-builtins"] = filename
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertTrue(os.path.isfile(filename))
    src = self._MakePyFile("""\
      import __future__
      import sys
      import collections
      import typing
    """)
    # Use builtins pickle
    self._ResetPytypeArgs()
    self._SetUpChecking(src)
    self.pytype_args["--precompiled-builtins"] = filename
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testUseBuiltinsAndImportMap(self):
    """Test for --generate-builtins."""
    filename = self._TmpPath("builtins.pickle")
    # Generate builtins pickle
    self.pytype_args["--generate-builtins"] = filename
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)
    self.assertTrue(os.path.isfile(filename))
    # input files
    canary = "import pytypecanary" if typeshed.Typeshed.MISSING_FILE else ""
    src = self._MakePyFile("""\
      import __future__
      import sys
      import collections
      import typing
      import foo
      import csv
      import ctypes
      import xml.etree.ElementTree as ElementTree
      import md5
      %s
      x = foo.x
      y = csv.writer
      z = md5.new
    """ % canary)
    pyi = self._MakeFile("""\
      import datetime
      x = ...  # type: datetime.tzinfo
    """, extension=".pyi")
    # Use builtins pickle with an imports map
    self._ResetPytypeArgs()
    self._SetUpChecking(src)
    self.pytype_args["--precompiled-builtins"] = filename
    self.pytype_args["--imports_info"] = self._MakeFile("""\
      typing /dev/null
      foo %s
    """ % pyi, extension="")
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=False)

  def testBuiltinsDeterminism2(self):
    f1, f2 = self._GenerateBuiltinsTwice("2.7")
    self.assertBuiltinsPickleEqual(f1, f2)

  def testBuiltinsDeterminism3(self):
    f1, f2 = self._GenerateBuiltinsTwice("3.6")
    self.assertBuiltinsPickleEqual(f1, f2)

  def testTimeout(self):
    # Note: At the time of this writing, pickling builtins takes well over one
    # second (~10s). If it ever was to get faster, this test would become flaky.
    self.pytype_args["--timeout"] = 1
    self.pytype_args["--generate-builtins"] = self._TmpPath("builtins.pickle")
    self._RunPytype(self.pytype_args)
    self.assertOutputStateMatches(stdout=False, stderr=False, returncode=True)


def main():
  unittest.main()


if __name__ == "__main__":
  main()
