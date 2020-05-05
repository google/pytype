# coding=utf8
"""Tests for directors.py."""

from pytype import directors
from pytype import errors
from pytype.tests import test_utils
import six
import unittest

_TEST_FILENAME = "my_file.py"


class LineSetTest(unittest.TestCase):

  def test_no_ranges(self):
    lines = directors._LineSet()
    lines.set_line(2, True)
    self.assertNotIn(0, lines)
    self.assertNotIn(1, lines)
    self.assertIn(2, lines)
    self.assertNotIn(3, lines)

  def test_closed_range(self):
    lines = directors._LineSet()
    lines.start_range(2, True)
    lines.start_range(4, False)
    self.assertNotIn(1, lines)
    self.assertIn(2, lines)
    self.assertIn(3, lines)
    self.assertNotIn(4, lines)
    self.assertNotIn(1000, lines)

  def test_open_range(self):
    lines = directors._LineSet()
    lines.start_range(2, True)
    lines.start_range(4, False)
    lines.start_range(7, True)
    self.assertNotIn(1, lines)
    self.assertIn(2, lines)
    self.assertIn(3, lines)
    self.assertNotIn(4, lines)
    self.assertNotIn(5, lines)
    self.assertNotIn(6, lines)
    self.assertIn(7, lines)
    self.assertIn(1000, lines)

  def test_range_at_zero(self):
    lines = directors._LineSet()
    lines.start_range(0, True)
    lines.start_range(3, False)
    self.assertNotIn(-1, lines)
    self.assertIn(0, lines)
    self.assertIn(1, lines)
    self.assertIn(2, lines)
    self.assertNotIn(3, lines)

  def test_line_overrides_range(self):
    lines = directors._LineSet()
    lines.start_range(2, True)
    lines.start_range(5, False)
    lines.set_line(3, False)
    self.assertIn(2, lines)
    self.assertNotIn(3, lines)
    self.assertIn(4, lines)

  def test_redundant_range(self):
    lines = directors._LineSet()
    lines.start_range(2, True)
    lines.start_range(3, True)
    lines.start_range(5, False)
    lines.start_range(9, False)
    self.assertNotIn(1, lines)
    self.assertIn(2, lines)
    self.assertIn(3, lines)
    self.assertIn(4, lines)
    self.assertNotIn(5, lines)
    self.assertNotIn(9, lines)
    self.assertNotIn(1000, lines)

  def test_enable_disable_on_same_line(self):
    lines = directors._LineSet()
    lines.start_range(2, True)
    lines.start_range(2, False)
    lines.start_range(3, True)
    lines.start_range(5, False)
    lines.start_range(5, True)
    self.assertNotIn(2, lines)
    self.assertIn(3, lines)
    self.assertIn(4, lines)
    self.assertIn(5, lines)
    self.assertIn(1000, lines)

  def test_decreasing_lines_not_allowed(self):
    lines = directors._LineSet()
    self.assertRaises(ValueError, lines.start_range, -100, True)
    lines.start_range(2, True)
    self.assertRaises(ValueError, lines.start_range, 1, True)


class DirectorTestCase(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    super(DirectorTestCase, cls).setUpClass()
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
    self.assertEqual(
        expected,
        self._director.should_report_error(error))


class DirectorTest(DirectorTestCase):

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

  def test_ignore_one_line_mypy_style(self):
    self._create("""
    # line 2
    x = 123  # type: ignore[arg-type]
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(True, 4)

  def test_utf8(self):
    self._create("""
    x = u"abc□def\n"
    """)

  def test_ignore_extra_characters(self):
    self._create("""
    # line 2
    x = 123  # # type: ignore
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
    self._should_report(False, None)  # No line number.
    self._should_report(False, 0)  # line number 0.

  def test_disable(self):
    self._create("""
    # line 2
    x = 123  # pytype: disable=test-error
    # line 4
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(True, 4)

  def test_disable_extra_characters(self):
    self._create("""
    # line 2
    x = 123  # # pytype: disable=test-error
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

  def test_enable_after_disable(self):
    self._create("""
    # line 2
    # pytype: disable=test-error
    # line 4
    # pytype: enable=test-error
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(False, 4)
    self._should_report(True, 5)
    self._should_report(True, 100)

  def test_enable_one_line(self):
    self._create("""
    # line 2
    # pytype: disable=test-error
    # line 4
    x = 123 # pytype: enable=test-error
    """)
    self._should_report(True, 2)
    self._should_report(False, 3)
    self._should_report(False, 4)
    self._should_report(True, 5)
    self._should_report(False, 6)
    self._should_report(False, 100)

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

  def test_multiple_directives(self):
    self._create("""
    x = 123  # sometool: directive=whatever # pytype: disable=test-error
    """)
    self._should_report(False, 2)

  def test_error_at_line_0(self):
    self._create("""
    x = "foo"
    # pytype: disable=attribute-error
    """)
    self._should_report(False, 0, error_name="attribute-error")

  def test_disable_without_space(self):
    self._create("""
    # line 2
    x = 123  # pytype:disable=test-error
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
      self.assertEqual(_TEST_FILENAME, error._filename)
      self.assertEqual(1, error.lineno)
      six.assertRegex(self, str(error), message_regex)

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

  def test_type_comments(self):
    self._create("""
    x = None  # type: int
    y = None  # allow extra comments # type: str
    z = None  # type: int  # and extra comments after, too
    a = None  # type:int  # without a space
    # type: (int, float) -> str
    # comment with embedded # type: should-be-discarded
    """)
    self.assertEqual({
        2: "int",
        3: "str",
        4: "int",
        5: "int",
        6: "(int, float) -> str",
    }, self._director.type_comments)

  def test_strings_that_look_like_directives(self):
    # Line 2 is a string, not a type comment.
    # Line 4 has a string and a comment.
    self._create("""
    s = "# type: int"
    x = None  # type: float
    y = "# type: int"  # type: str
    """)
    self.assertEqual({
        3: "float",
        4: "str",
    }, self._director.type_comments)

  def test_type_comment_on_multiline_value(self):
    # should_be_ignored will be filtered out later by adjust_line_numbers.
    self._create("""
    v = [
      ("hello",
       "world",  # type: should_be_ignored

      )
    ]  # type: dict
    """)
    self.assertEqual({
        4: "should_be_ignored",
        7: "dict",
    }, self._director.type_comments)

  def test_type_comment_with_trailing_comma(self):
    self._create("""
    v = [
      ("hello",
       "world"
      ),
    ]  # type: dict
    w = [
      ["hello",
       "world"
      ],  # some comment
    ]  # type: dict
    """)
    self.assertEqual({
        6: "dict",
        11: "dict",
    }, self._director.type_comments)

  def test_decorators(self):
    self._create("""
      class A:
        '''
        @decorator in a docstring
        '''
        @real_decorator
        def f(x):
          x = foo @ bar @ baz

        @decorator(
            x, y
        )

        def bar():
          pass
    """)
    self.assertEqual({
        7,  # real_decorator
        14  # decorator
    }, self._director._decorators)

  def test_stacked_decorators(self):
    self._create("""
      @decorator(
          x, y
      )

      @foo

      class A:
          pass
    """)
    self.assertEqual({
        8  # foo
    }, self._director._decorators)


@test_utils.skipBeforePy((3, 6), reason="Variable annotations are 3.6+.")
class VariableAnnotationsTest(DirectorTestCase):

  def test_annotations(self):
    self._create("""
      v1: int = 0
      def f():
        v2: str = ''
    """)
    self.assertEqual({2: "int", 4: "str"}, self._director.annotations)

  def test_precedence(self):
    self._create("v: int = 0  # type: str")
    # Variable annotations take precedence. vm.py's _FindIgnoredTypeComments
    # warns about the ignored comment.
    self.assertEqual({1: "int"}, self._director.annotations)

  def test_parameter_annotation(self):
    # director.annotations contains only variable annotations and function type
    # comments, so a parameter annotation should be ignored.
    self._create("""
      def f(
          x: int = 0):
        pass
    """)
    self.assertFalse(self._director.annotations)

  @unittest.skip(
      "directors._VariableAnnotation assumes a variable annotation starts at "
      "the beginning of the line.")
  def test_multistatement_line(self):
    self._create("""
      if __random__: v1: int = 0
      else: v2: str = ''
    """)
    self.assertEqual({2: "int", 3: "str"}, self._director.annotations)

  def test_multistatement_line_no_annotation(self):
    self._create("""
      if __random__: v = 0
      else: v = 1
    """)
    self.assertFalse(self._director.annotations)

  def test_comment_is_not_an_annotation(self):
    self._create("# TODO(b/xxx): pylint: disable=invalid-name")
    self.assertFalse(self._director.annotations)

  def test_string_is_not_an_annotation(self):
    self._create("""
      logging.info('%s: completed: response=%s',  s1, s2)
      f(':memory:', bar=baz)
    """)
    self.assertFalse(self._director.annotations)

  def test_multiline_annotation(self):
    self._create("""
      v: Callable[
          [], int] = None
    """)
    self.assertEqual({3: "Callable[[], int]"}, self._director.annotations)

  def test_multiline_assignment(self):
    self._create("""
      v: List[int] = [
          0,
          1,
      ]
    """)
    self.assertEqual({5: "List[int]"}, self._director.annotations)

  def test_complicated_annotation(self):
    self._create("v: int if __random__ else str = None")
    self.assertEqual(
        {1: "int if __random__ else str"}, self._director.annotations)

  def test_colon_in_value(self):
    self._create("v: Dict[str, int] = {x: y}")
    self.assertEqual({1: "Dict[str, int]"}, self._director.annotations)

  def test_equals_sign_in_value(self):
    self._create("v = {x: f(y=0)}")
    self.assertFalse(self._director.annotations)

  def test_annotation_after_comment(self):
    self._create("""
      # comment
      v: int = 0
    """)
    self.assertEqual({3: "int"}, self._director.annotations)


if __name__ == "__main__":
  unittest.main()
