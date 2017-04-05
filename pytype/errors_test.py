"""Test errors.py."""

import collections
import csv

from pytype import errors
from pytype import utils

import unittest

_TEST_ERROR = "test-error"
_MESSAGE = "an error message"

FakeCode = collections.namedtuple("FakeCode", "co_filename co_name")


class FakeOpcode(object):

  def __init__(self, filename, line, methodname):
    self.code = FakeCode(filename, methodname)
    self.line = line


class ErrorTest(unittest.TestCase):

  @errors._error_name(_TEST_ERROR)
  def test_init(self):
    e = errors.Error(errors.SEVERITY_ERROR, _MESSAGE, filename="foo.py",
                     lineno=123, column=2, linetext="hello", methodname="foo")
    self.assertEquals(errors.SEVERITY_ERROR, e._severity)
    self.assertEquals(_MESSAGE, e._message)
    self.assertEquals(e._name, _TEST_ERROR)
    self.assertEquals("foo.py", e._filename)
    self.assertEquals(123, e._lineno)
    self.assertEquals(2, e._column)
    self.assertEquals("hello", e._linetext)
    self.assertEquals("foo", e._methodname)

  @errors._error_name(_TEST_ERROR)
  def test_at_opcode(self):
    # Opcode of None.
    e = errors.Error.at_opcode(None, errors.SEVERITY_ERROR, _MESSAGE)
    self.assertEquals(errors.SEVERITY_ERROR, e._severity)
    self.assertEquals(_MESSAGE, e._message)
    self.assertEquals(e._name, _TEST_ERROR)
    self.assertEquals(None, e._filename)
    self.assertEquals(0, e._lineno)
    self.assertEquals(None, e._column)
    self.assertEquals(None, e._linetext)
    self.assertEquals(None, e._methodname)
    # Opcode of None.
    op = FakeOpcode("foo.py", 123, "foo")
    e = errors.Error.at_opcode(op, errors.SEVERITY_ERROR, _MESSAGE)
    self.assertEquals(errors.SEVERITY_ERROR, e._severity)
    self.assertEquals(_MESSAGE, e._message)
    self.assertEquals(e._name, _TEST_ERROR)
    self.assertEquals("foo.py", e._filename)
    self.assertEquals(123, e._lineno)
    self.assertEquals(None, e._column)
    self.assertEquals(None, e._linetext)
    self.assertEquals("foo", e._methodname)

  def test__error_name(self):
    # This should be true as long as at least one method is annotated with
    # _error_name(_TEST_ERROR).
    self.assertIn(_TEST_ERROR, errors._ERROR_NAMES)

  def test_no_error_name(self):
    # It is illegal to create an error outside of an @error_name annotation.
    self.assertRaises(AssertionError, errors.Error, errors.SEVERITY_ERROR,
                      _MESSAGE)

  @errors._error_name(_TEST_ERROR)
  def test_str(self):
    e = errors.Error(errors.SEVERITY_ERROR, _MESSAGE, filename="foo.py",
                     lineno=123, column=2, linetext="hello", methodname="foo")
    expected = 'File "foo.py", line 123, in foo: an error message [test-error]'
    self.assertEquals(expected, str(e))

  def test_from_csv_row(self):
    row = ["a.py", "123", "index-error", "This is an error",
           "with\nsome\ndetails: 1, 2, 3"]
    error = errors.Error.from_csv_row(row)
    self.assertEquals(error.filename, row[0])
    self.assertEquals(error.lineno, int(row[1]))
    self.assertEquals(error.name, row[2])
    self.assertEquals(error.message, row[3] + "\n" + row[4])

  @errors._error_name(_TEST_ERROR)
  def test_write_to_csv(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    message, details = "This is an error", "with\nsome\ndetails: \"1\", 2, 3"
    errorlog.error(op, message, details + "0")
    errorlog.error(op, message, details + "1")
    with utils.Tempdir() as d:
      filename = d.create_file("errors.csv")
      error = errorlog.print_to_csv_file(filename)
      with open(filename, "rb") as fi:
        rows = list(csv.reader(fi, delimiter=","))
        self.assertEquals(2, len(rows))
        for i, row in enumerate(rows):
          error = errors.Error.from_csv_row(row)
          self.assertEquals(error.filename, "foo.py")
          self.assertEquals(error.lineno, 123)
          self.assertEquals(error.name, _TEST_ERROR)
          self.assertEquals(error.message, message + "\n" + details + str(i))


class ErrorLogBaseTest(unittest.TestCase):

  @errors._error_name(_TEST_ERROR)
  def test_error(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    errorlog.error(op, "unknown attribute %s" % "xyz")
    self.assertEquals(1, len(errorlog))
    e = list(errorlog)[0]  # iterate the log and save the first error.
    self.assertEquals(errors.SEVERITY_ERROR, e._severity)
    self.assertEquals("unknown attribute xyz", e._message)
    self.assertEquals(e._name, _TEST_ERROR)
    self.assertEquals("foo.py", e._filename)

  @errors._error_name(_TEST_ERROR)
  def test_error_with_details(self):
    errorlog = errors.ErrorLog()
    errorlog.error(None, "My message", "one\ntwo")
    expected = "My message [test-error]\n  one\n  two\n"
    self.assertEquals(expected, str(errorlog))

  @errors._error_name(_TEST_ERROR)
  def test_warn(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    errorlog.warn(op, "unknown attribute %s", "xyz")
    self.assertEquals(1, len(errorlog))
    e = list(errorlog)[0]  # iterate the log and save the first error.
    self.assertEquals(errors.SEVERITY_WARNING, e._severity)
    self.assertEquals("unknown attribute xyz", e._message)
    self.assertEquals(e._name, _TEST_ERROR)
    self.assertEquals("foo.py", e._filename)

  @errors._error_name(_TEST_ERROR)
  def test_has_error(self):
    errorlog = errors.ErrorLog()
    self.assertFalse(errorlog.has_error())
    # A warning is part of the error log, but isn't severe.
    errorlog.warn(None, "A warning")
    self.assertEquals(1, len(errorlog))
    self.assertFalse(errorlog.has_error())
    # An error is severe.
    errorlog.error(None, "An error")
    self.assertEquals(2, len(errorlog))
    self.assertTrue(errorlog.has_error())


if __name__ == "__main__":
  unittest.main()
