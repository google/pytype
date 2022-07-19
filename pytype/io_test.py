"""Tests for io.py."""

import contextlib
import io as builtins_io
import sys
import textwrap
import traceback

from pytype import config
from pytype import io
from pytype.platform_utils import path_utils
from pytype.platform_utils import tempfile as compatible_tempfile
from pytype.pytd import pytd

import unittest


class IOTest(unittest.TestCase):
  """Test IO functions."""

  def test_read_source_file_utf8(self):
    with self._tmpfile("abc□def\n") as f:
      self.assertEqual(io.read_source_file(f.name), "abc□def\n")

  @contextlib.contextmanager
  def _tmpfile(self, contents):
    tempfile_options = {"mode": "w", "suffix": ".txt", "encoding": "utf-8"}
    with compatible_tempfile.NamedTemporaryFile(**tempfile_options) as f:
      f.write(contents)
      f.flush()
      yield f

  def test_wrap_pytype_exceptions(self):
    with self.assertRaises(ValueError):
      with io.wrap_pytype_exceptions(ValueError, "foo.py"):
        io.read_source_file("missing_file")

  def test_wrap_pytype_exception_traceback(self):
    class CustomError(Exception):
      pass

    def called_function():
      raise OSError("error!")

    def calling_function():
      called_function()

    err = None
    trace = None
    try:
      with io.wrap_pytype_exceptions(CustomError, "foo.py"):
        calling_function()
    except CustomError as e:
      err = e
      _, _, tb = sys.exc_info()
      trace = traceback.format_tb(tb)

    self.assertIn("OSError: error!", err.args[0])
    self.assertTrue(any("in calling_function" in x for x in trace))

  def test_check_py(self):
    errorlog = io.check_py("undefined_var")
    error, = errorlog.unique_sorted_errors()
    self.assertEqual(error.name, "name-error")

  def test_check_py_with_options(self):
    options = config.Options.create(disable="name-error")
    errorlog = io.check_py("undefined_var", options)
    self.assertFalse(errorlog.unique_sorted_errors())

  def test_generate_pyi(self):
    errorlog, pyi_string, pytd_ast = io.generate_pyi("x = 42")
    self.assertFalse(errorlog.unique_sorted_errors())
    self.assertEqual(pyi_string, "x: int\n")
    self.assertIsInstance(pytd_ast, pytd.TypeDeclUnit)

  def test_generate_pyi_with_options(self):
    with self._tmpfile("x: int") as pyi:
      pyi_name, _ = path_utils.splitext(path_utils.basename(pyi.name))
      with self._tmpfile(
          f"{pyi_name} {pyi.name}") as imports_map:
        src = "import {mod}; y = {mod}.x".format(mod=pyi_name)
        options = config.Options.create(imports_map=imports_map.name)
        _, pyi_string, _ = io.generate_pyi(src, options)
    self.assertEqual(pyi_string,
                     f"import {pyi_name}\n\ny: int\n")

  def test_generate_pyi__overload_order(self):
    _, pyi_string, _ = io.generate_pyi(textwrap.dedent("""
      from typing import Any, overload
      @overload
      def f(x: None) -> None: ...
      @overload
      def f(x: Any) -> int: ...
      def f(x):
        return __any_object__
    """.lstrip("\n")))
    self.assertMultiLineEqual(pyi_string, textwrap.dedent("""
      from typing import overload

      @overload
      def f(x: None) -> None: ...
      @overload
      def f(x) -> int: ...
    """.lstrip("\n")))

  def test_check_or_generate_pyi__check(self):
    with self._tmpfile("") as f:
      options = config.Options.create(f.name, check=True)
      _, pyi_string, pytd_ast = io.check_or_generate_pyi(options)
    self.assertIsNone(pyi_string)
    self.assertIsNone(pytd_ast)

  def test_check_or_generate_pyi__generate(self):
    with self._tmpfile("") as f:
      options = config.Options.create(f.name, check=False)
      _, pyi_string, pytd_ast = io.check_or_generate_pyi(options)
    self.assertIsNotNone(pyi_string)
    self.assertIsNotNone(pytd_ast)

  def test_check_or_generate_pyi__open_function(self):
    def mock_open(filename, *args, **kwargs):
      if filename == "my_amazing_file.py":
        return builtins_io.StringIO("x = 0.0")
      else:
        return open(filename, *args, **kwargs)  # pylint: disable=consider-using-with
    options = config.Options.create(
        "my_amazing_file.py", check=False, open_function=mock_open)
    _, pyi_string, _ = io.check_or_generate_pyi(options)
    self.assertEqual(pyi_string, "x: float\n")

  def test_write_pickle(self):
    ast = pytd.TypeDeclUnit(None, (), (), (), (), ())
    options = config.Options.create(
        output="/dev/null" if sys.platform != "win32" else "NUL")
    io.write_pickle(ast, options)  # just make sure we don't crash


if __name__ == "__main__":
  unittest.main()
