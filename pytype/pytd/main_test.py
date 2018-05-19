"""Tests for pytd_tool (pytd/main.py)."""

import os
import sys
import textwrap
import unittest
from pytype import file_utils
from pytype.pytd import main as pytd_tool


class TestPytdTool(unittest.TestCase):
  """Test pytd/main.py."""

  def setUp(self):
    # Save the value of sys.argv (which will be restored in tearDown), so that
    # tests can overwrite it.
    self._sys_argv = sys.argv

  def tearDown(self):
    sys.argv = self._sys_argv

  def test_parse_options(self):
    options, filenames = pytd_tool.parse_options([
        "main.py", "--optimize", "--lossy", "--max-union=42", "--use-abcs",
        "--remove-mutable", "--python_version=3.6", "in.pytd", "out.pytd"])
    self.assertTrue(options.optimize)
    self.assertTrue(options.lossy)
    self.assertEqual(options.max_union, 42)
    self.assertTrue(options.use_abcs)
    self.assertTrue(options.remove_mutable)
    self.assertEqual(options.python_version, "3.6")
    self.assertListEqual(filenames, ["main.py", "in.pytd", "out.pytd"])

  def test_version_error(self):
    sys.argv = ["main.py", "--python_version=4.0"]
    with self.assertRaises(SystemExit):
      pytd_tool.main()

  def test_missing_input(self):
    sys.argv = ["main.py"]
    with self.assertRaises(SystemExit):
      pytd_tool.main()

  def test_parse_error(self):
    with file_utils.Tempdir() as d:
      inpath = d.create_file("in.pytd", "def f(x): str")  # malformed pytd
      sys.argv = ["main.py", inpath]
      with self.assertRaises(SystemExit):
        pytd_tool.main()

  def test_no_output(self):
    with file_utils.Tempdir() as d:
      inpath = d.create_file("in.pytd", "def f(x) -> str")
      # Not specifying an output is fine; the tool simply checks that the input
      # file is parseable.
      sys.argv = ["main.py", inpath]
      pytd_tool.main()

  def test_output(self):
    with file_utils.Tempdir() as d:
      src = textwrap.dedent("""
        @overload
        def f(x: int) -> str: ...
        @overload
        def f(x: str) -> str: ...
      """).strip()
      inpath = d.create_file("in.pytd", src)
      outpath = os.path.join(d.path, "out.pytd")
      sys.argv = ["main.py", inpath, outpath]
      pytd_tool.main()
      with open(outpath, "r") as f:
        self.assertMultiLineEqual(f.read(), src)

  def test_optimize(self):
    with file_utils.Tempdir() as d:
      inpath = d.create_file("in.pytd", """
        @overload
        def f(x: int) -> str: ...
        @overload
        def f(x: str) -> str: ...
      """)
      outpath = os.path.join(d.path, "out.pytd")
      sys.argv = ["main.py", "--optimize", inpath, outpath]
      pytd_tool.main()
      with open(outpath, "r") as f:
        self.assertMultiLineEqual(f.read(), textwrap.dedent("""
          from typing import Union

          def f(x: Union[int, str]) -> str: ...
        """).strip())


if __name__ == "__main__":
  unittest.main()
