# coding=utf8
"""Tests for io.py."""

import six
import sys
import tempfile
import traceback

from pytype import io

import unittest

class IOTest(unittest.TestCase):
  """Test IO functions."""

  def testReadSourceFileUtf8(self):
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

  def testWrapPytypeExceptions(self):
    with self.assertRaises(ValueError):
      with io.wrap_pytype_exceptions(ValueError, "foo.py"):
        io.read_source_file("missing_file")

  def testWrapPytypeExceptionTraceback(self):
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

if __name__ == "__main__":
  unittest.main()
