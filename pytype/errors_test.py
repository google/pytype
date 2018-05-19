"""Test errors.py."""

import collections
import csv
import os
import textwrap

from pytype import errors
from pytype import file_utils
from pytype import state as frame_state

import unittest

_TEST_ERROR = "test-error"
_MESSAGE = "an error message"

FakeCode = collections.namedtuple("FakeCode", "co_filename co_name")


class FakeOpcode(object):

  def __init__(self, filename, line, methodname):
    self.code = FakeCode(filename, methodname)
    self.line = line

  def to_stack(self):
    return [frame_state.SimpleFrame(self)]


def _fake_stack(length):
  return [frame_state.SimpleFrame(FakeOpcode("foo.py", i, "function%d" % i))
          for i in range(length)]


class ErrorTest(unittest.TestCase):

  @errors._error_name(_TEST_ERROR)
  def test_init(self):
    e = errors.Error(errors.SEVERITY_ERROR, _MESSAGE, filename="foo.py",
                     lineno=123, methodname="foo")
    self.assertEqual(errors.SEVERITY_ERROR, e._severity)
    self.assertEqual(_MESSAGE, e._message)
    self.assertEqual(e._name, _TEST_ERROR)
    self.assertEqual("foo.py", e._filename)
    self.assertEqual(123, e._lineno)
    self.assertEqual("foo", e._methodname)

  @errors._error_name(_TEST_ERROR)
  def test_with_stack(self):
    # Opcode of None.
    e = errors.Error.with_stack(None, errors.SEVERITY_ERROR, _MESSAGE)
    self.assertEqual(errors.SEVERITY_ERROR, e._severity)
    self.assertEqual(_MESSAGE, e._message)
    self.assertEqual(e._name, _TEST_ERROR)
    self.assertEqual(None, e._filename)
    self.assertEqual(0, e._lineno)
    self.assertEqual(None, e._methodname)
    # Opcode of None.
    op = FakeOpcode("foo.py", 123, "foo")
    e = errors.Error.with_stack(op.to_stack(), errors.SEVERITY_ERROR, _MESSAGE)
    self.assertEqual(errors.SEVERITY_ERROR, e._severity)
    self.assertEqual(_MESSAGE, e._message)
    self.assertEqual(e._name, _TEST_ERROR)
    self.assertEqual("foo.py", e._filename)
    self.assertEqual(123, e._lineno)
    self.assertEqual("foo", e._methodname)

  @errors._error_name(_TEST_ERROR)
  def test_no_traceback_stack_len_1(self):
    # Stack of length 1
    op = FakeOpcode("foo.py", 123, "foo")
    error = errors.Error.with_stack(op.to_stack(), errors.SEVERITY_ERROR, "")
    self.assertIsNone(error._traceback)

  @errors._error_name(_TEST_ERROR)
  def test_no_traceback_no_opcode(self):
    # Frame without opcode
    op = FakeOpcode("foo.py", 123, "foo")
    stack = [frame_state.SimpleFrame(), frame_state.SimpleFrame(op)]
    error = errors.Error.with_stack(stack, errors.SEVERITY_ERROR, "")
    self.assertIsNone(error._traceback)

  @errors._error_name(_TEST_ERROR)
  def test_traceback(self):
    stack = _fake_stack(errors.MAX_TRACEBACK_LENGTH + 1)
    error = errors.Error.with_stack(stack, errors.SEVERITY_ERROR, "")
    self.assertMultiLineEqual(error._traceback, textwrap.dedent("""\
      Traceback:
        line 0, in function0
        line 1, in function1
        line 2, in function2"""))

  @errors._error_name(_TEST_ERROR)
  def test_truncated_traceback(self):
    stack = _fake_stack(errors.MAX_TRACEBACK_LENGTH + 2)
    error = errors.Error.with_stack(stack, errors.SEVERITY_ERROR, "")
    self.assertMultiLineEqual(error._traceback, textwrap.dedent("""\
      Traceback:
        line 0, in function0
        ...
        line 3, in function3"""))

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
                     lineno=123, methodname="foo")
    self.assertEqual(
        'File "foo.py", line 123, in foo: an error message [test-error]',
        str(e))

  @errors._error_name(_TEST_ERROR)
  def test_write_to_csv(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    message, details = "This is an error", "with\nsome\ndetails: \"1\", 2, 3"
    errorlog.error(op.to_stack(), message, details + "0")
    errorlog.error(op.to_stack(), message, details + "1")
    with file_utils.Tempdir() as d:
      filename = d.create_file("errors.csv")
      errorlog.print_to_csv_file(filename)
      with open(filename, "r") as fi:
        rows = list(csv.reader(fi, delimiter=","))
        self.assertEqual(2, len(rows))
        for i, row in enumerate(rows):
          filename, lineno, name, actual_message, actual_details = row
          self.assertEqual(filename, "foo.py")
          self.assertEqual(lineno, "123")
          self.assertEqual(name, _TEST_ERROR)
          self.assertEqual(actual_message, message)
          self.assertEqual(actual_details, details + str(i))

  @errors._error_name(_TEST_ERROR)
  def test_write_to_csv_with_traceback(self):
    errorlog = errors.ErrorLog()
    stack = _fake_stack(2)
    errorlog.error(stack, "", "some\ndetails")
    with file_utils.Tempdir() as d:
      filename = d.create_file("errors.csv")
      errorlog.print_to_csv_file(filename)
      with open(filename, "r") as fi:
        (_, _, _, _, actual_details), = list(csv.reader(fi, delimiter=","))
        self.assertMultiLineEqual(actual_details, textwrap.dedent("""\
          some
          details

          Traceback:
            line 0, in function0"""))


class ErrorLogBaseTest(unittest.TestCase):

  @errors._error_name(_TEST_ERROR)
  def test_error(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    errorlog.error(op.to_stack(), "unknown attribute %s" % "xyz")
    self.assertEqual(1, len(errorlog))
    e = list(errorlog)[0]  # iterate the log and save the first error.
    self.assertEqual(errors.SEVERITY_ERROR, e._severity)
    self.assertEqual("unknown attribute xyz", e._message)
    self.assertEqual(e._name, _TEST_ERROR)
    self.assertEqual("foo.py", e._filename)

  @errors._error_name(_TEST_ERROR)
  def test_error_with_details(self):
    errorlog = errors.ErrorLog()
    errorlog.error(None, "My message", "one\ntwo")
    self.assertEqual(textwrap.dedent("""\
        My message [test-error]
          one
          two
        """), str(errorlog))

  @errors._error_name(_TEST_ERROR)
  def test_warn(self):
    errorlog = errors.ErrorLog()
    op = FakeOpcode("foo.py", 123, "foo")
    errorlog.warn(op.to_stack(), "unknown attribute %s", "xyz")
    self.assertEqual(1, len(errorlog))
    e = list(errorlog)[0]  # iterate the log and save the first error.
    self.assertEqual(errors.SEVERITY_WARNING, e._severity)
    self.assertEqual("unknown attribute xyz", e._message)
    self.assertEqual(e._name, _TEST_ERROR)
    self.assertEqual("foo.py", e._filename)

  @errors._error_name(_TEST_ERROR)
  def test_has_error(self):
    errorlog = errors.ErrorLog()
    self.assertFalse(errorlog.has_error())
    # A warning is part of the error log, but isn't severe.
    errorlog.warn(None, "A warning")
    self.assertEqual(1, len(errorlog))
    self.assertFalse(errorlog.has_error())
    # An error is severe.
    errorlog.error(None, "An error")
    self.assertEqual(2, len(errorlog))
    self.assertTrue(errorlog.has_error())

  @errors._error_name(_TEST_ERROR)
  def test_duplicate_error_no_traceback(self):
    errorlog = errors.ErrorLog()
    stack = _fake_stack(2)
    errorlog.error(stack, "error")  # traceback
    errorlog.error(stack[-1:], "error")  # no traceback
    # Keep the error with no traceback.
    unique_errors = errorlog.unique_sorted_errors()
    self.assertEqual(1, len(unique_errors))
    self.assertIsNone(unique_errors[0]._traceback)

  @errors._error_name(_TEST_ERROR)
  def test_duplicate_error_shorter_traceback(self):
    errorlog = errors.ErrorLog()
    stack = _fake_stack(3)
    errorlog.error(stack, "error")  # longer traceback
    errorlog.error(stack[-2:], "error")  # shorter traceback
    # Keep the error with a shorter traceback.
    unique_errors = errorlog.unique_sorted_errors()
    self.assertEqual(1, len(unique_errors))
    self.assertMultiLineEqual(unique_errors[0]._traceback, textwrap.dedent("""\
      Traceback:
        line 1, in function1"""))

  @errors._error_name(_TEST_ERROR)
  def test_unique_errors(self):
    errorlog = errors.ErrorLog()
    current_frame = frame_state.SimpleFrame(FakeOpcode("foo.py", 123, "foo"))
    backframe1 = frame_state.SimpleFrame(FakeOpcode("foo.py", 1, "bar"))
    backframe2 = frame_state.SimpleFrame(FakeOpcode("foo.py", 2, "baz"))
    errorlog.error([backframe1, current_frame], "error")
    errorlog.error([backframe2, current_frame], "error")
    # Keep both errors, since the tracebacks are different.
    unique_errors = errorlog.unique_sorted_errors()
    self.assertEqual(2, len(unique_errors))
    self.assertSetEqual(set(errorlog), set(unique_errors))




if __name__ == "__main__":
  unittest.main()
