# coding=utf8
"""Tests for io.py."""

import os
import sys
import tempfile
import traceback

from pytype import config
from pytype import io
from pytype.pytd import pytd
import six

import unittest


class IOTest(unittest.TestCase):
  """Test IO functions."""

  def test_read_source_file_utf8(self):
    with self._tmpfile(u"abc□def\n") as f:
      self.assertEqual(io.read_source_file(f.name), u"abc□def\n")

  def _tmpfile(self, contents):
    tempfile_options = {"mode": "w", "suffix": ".txt"}
    if six.PY3:
      tempfile_options.update({"encoding": "utf-8"})
    f = tempfile.NamedTemporaryFile(**tempfile_options)
    if six.PY3:
      f.write(contents)
    else:
      f.write(contents.encode("utf-8"))
    f.flush()
    return f

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
    with self._tmpfile("undefined_var") as f:
      errorlog = io.check_py(f.name)
    error, = errorlog.unique_sorted_errors()
    self.assertEqual(error.name, "name-error")

  def test_check_py_with_options(self):
    with self._tmpfile("undefined_var") as f:
      options = config.Options.create(f.name, disable="name-error")
      errorlog = io.check_py(f.name, options)
    self.assertFalse(errorlog.unique_sorted_errors())

  def test_generate_pyi(self):
    with self._tmpfile("x = 42") as f:
      errorlog, pyi_string, pytd_ast = io.generate_pyi(f.name)
    self.assertFalse(errorlog.unique_sorted_errors())
    self.assertEqual(pyi_string, "x: int\n")
    self.assertIsInstance(pytd_ast, pytd.TypeDeclUnit)

  def test_generate_pyi_with_options(self):
    with self._tmpfile("x: int") as pyi:
      pyi_name, _ = os.path.splitext(os.path.basename(pyi.name))
      with self._tmpfile(
          "{mod} {path}".format(mod=pyi_name, path=pyi.name)) as imports_map:
        with self._tmpfile(
            "import {mod}; y = {mod}.x".format(mod=pyi_name)) as py:
          options = config.Options.create(py.name, imports_map=imports_map.name)
          _, pyi_string, _ = io.generate_pyi(py.name, options)
    self.assertEqual(pyi_string, "{mod}: module\ny: int\n".format(mod=pyi_name))

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

  def test_write_pickle(self):
    ast = pytd.TypeDeclUnit(None, (), (), (), (), ())
    options = config.Options.create(output="/dev/null")
    io.write_pickle(ast, options)  # just make sure we don't crash


if __name__ == "__main__":
  unittest.main()
