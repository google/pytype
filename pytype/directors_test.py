"""Tests for directors.py."""


from pytype import directors
from pytype import errors
import unittest

_TEST_FILENAME = "my_file.py"


class LineSetTest(unittest.TestCase):

  def test_basic_operation(self):
    lines = directors._LineSet()
    lines.add(7)
    self.assertNotIn(6, lines)
    self.assertIn(7, lines)
    self.assertNotIn(8, lines)
    self.assertNotIn(100, lines)
    lines.add(100, open_ended=True)
    self.assertNotIn(99, lines)
    self.assertIn(100, lines)
    self.assertIn(101, lines)

  def test_increasing_limit(self):
    lines = directors._LineSet()
    lines.add(100, open_ended=True)
    lines.add(200, open_ended=True)
    self.assertNotIn(99, lines)
    self.assertIn(100, lines)
    self.assertIn(200, lines)
    self.assertIn(201, lines)

  def test_decreasing_limit(self):
    lines = directors._LineSet()
    lines.add(200, open_ended=True)
    lines.add(100, open_ended=True)
    self.assertNotIn(99, lines)
    self.assertIn(100, lines)
    self.assertIn(200, lines)
    self.assertIn(201, lines)


class DirectorTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    # Invoking the _error_name decorator will register the name as a valid
    # error name.
    for name in ["test-error", "test-other-error"]:
      errors._error_name(name)

  def _create(self, src, disable=()):
    self._errorlog = errors.ErrorLog()
    self._director = directors.Director(src, self._errorlog, _TEST_FILENAME,
                                        disable)

  def _should_report(self, expected, lineno, error_name="test-error",
                     filename=_TEST_FILENAME):
    error = errors.Error.for_test(
        errors.SEVERITY_ERROR, "message", error_name, filename=filename,
        lineno=lineno)
    self.assertEquals(
        expected,
        self._director.should_report_error(error))

  def test_ignore_globally(self):
    self._create("", ["my-error"])
    self._should_report(False, 42, error_name="my-error")

  def test_ignore_one_line(self):
    self._create("""
    # line 2
    x = 123  # type: ignore
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(True, 4)

  def test_ignore_until_end(self):
    self._create("""
    # line 2
    # type: ignore
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(False, 4)

  def test_out_of_scope(self):
    self._create("""
    # type: ignore
    """)
    self._should_report(False, 2)
    self._should_report(True, 2, filename=None)  # No file.
    self._should_report(True, 2, filename="some_other_file.py")  # Other file.
    self._should_report(True, None)  # No line number.

  def test_disable(self):
    self._create("""
    # line 2
    x = 123  # pytype: disable=test-error
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(True, 4)

  def test_disable_until_end(self):
    self._create("""
    # line 2
    # pytype: disable=test-error
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(False, 4)

  def test_disable_other_error(self):
    self._create("""
    # line 2
    x = 123  # pytype: disable=test-other-error
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(True, 3)
    self._should_report(False, 3, error_name="test-other-error")
    self._should_report(True, 4)

  def test_disable_multiple_error(self):
    self._create("""
    # line 2
    x = 123  # pytype: disable=test-error,test-other-error
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(False, 3, error_name="test-other-error")
    self._should_report(True, 4)

  def test_disable_all(self):
    self._create("""
    # line 2
    x = 123  # pytype: disable=*
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(True, 4)

  def test_invalid_disable(self):
    def check_warning(message_regex, text):
      self._create(text)
      self.assertLessEqual(1, len(self._errorlog))
      error = list(self._errorlog)[0]
      self.assertEquals(_TEST_FILENAME, error._filename)
      self.assertEquals(1, error.lineno)
      self.assertRegexpMatches(str(error), message_regex)

    check_warning("Unknown pytype directive.*disalbe.*",
                  "# pytype: disalbe=test-error")
    check_warning("Invalid error name.*bad-error-name.*",
                  "# pytype: disable=bad-error-name")
    check_warning("Invalid directive syntax",
                  "# pytype: disable")
    check_warning("Invalid directive syntax",
                  "# pytype: ")
    check_warning("Unknown pytype directive.*foo.*",
                  "# pytype: disable=test-error foo=bar")
    # Spaces aren't allowed in the comma-separated value list.
    check_warning("Invalid directive syntax",
                  "# pytype: disable=test-error ,test-other-error")
    # This will actually result in two warnings: the first because the
    # empty string isn't a valid error name, the second because
    # test-other-error isn't a valid command.  We only verify the first
    # warning.
    check_warning("Invalid error name",
                  "# pytype: disable=test-error, test-other-error")


if __name__ == "__main__":
  unittest.main()
