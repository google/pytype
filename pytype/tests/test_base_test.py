"""Tests for our test framework."""

from pytype import file_utils
from pytype import utils
from pytype.tests import test_base
from pytype.tests import test_utils
import six


class ErrorLogTest(test_base.TargetIndependentTest):

  def _lineno(self, line):
    if self.python_version == (2, 7) and utils.USE_ANNOTATIONS_BACKPORT:
      return line + 1
    return line

  def test_error_comments(self):
    err = self.CheckWithErrors("""
      a = 10  # a random comment
      b = "hello" + 3  # unsupported-operands[.mark]
      c = (10).foo  # attribute-error
      d = int(int)  # wrong-arg-types[.another_mark]
    """)
    self.assertEqual(
        {mark: (e.lineno, e.name) for mark, e in err.marks.items()},
        {".mark": (self._lineno(2), "unsupported-operands"),
         ".another_mark": (self._lineno(4), "wrong-arg-types")})
    self.assertEqual(err.expected, {
        self._lineno(2): [("unsupported-operands", ".mark")],
        self._lineno(3): [("attribute-error", None)],
        self._lineno(4): [("wrong-arg-types", ".another_mark")]})

  def test_multiple_errors_one_line(self):
    err = self.CheckWithErrors("""
      x = (10).foo, "hello".foo  # attribute-error[e1]  # attribute-error[e2]
    """)
    line = self._lineno(1)
    self.assertEqual(err.expected, {line: [("attribute-error", "e1"),
                                           ("attribute-error", "e2")]})
    six.assertCountEqual(self, err.marks, ["e1", "e2"])
    self.assertIn("on int", err.marks["e1"].message)
    self.assertIn("on str", err.marks["e2"].message)

  def test_populate_marks(self):
    # Test that assert_error_regexes populates self.marks if not already done.
    errorlog = test_utils.TestErrorLog("x = 0")
    self.assertIsNone(errorlog.marks)
    self.assertErrorRegexes(errorlog, {})
    self.assertIsNotNone(errorlog.marks)

  def test_duplicate_mark(self):
    with self.assertRaises(AssertionError) as ctx:
      self.CheckWithErrors("x = 0  # attribute-error[e]  # attribute-error[e]")
    self.assertEqual(str(ctx.exception), "Mark e already used")

  def test_error_matching(self):
    err = self.CheckWithErrors("""
      a = 10
      b = "hello"
      c = a + b  # unsupported-operands
      d = a.foo()  # attribute-error[.mark]
    """)
    self.assertErrorRegexes(err, {".mark": ".*foo.*"})

  def test_mismatched_error(self):
    with self.assertRaises(AssertionError) as ctx:
      self.CheckWithErrors("(10).foo  # wrong-arg-types")
    self.assertIn("Error does not match", str(ctx.exception))

  def test_unexpected_error(self):
    with self.assertRaises(AssertionError) as ctx:
      self.CheckWithErrors("""
        (10).foo  # attribute-error
        "hello".foo
      """)
    self.assertIn("Unexpected error", str(ctx.exception))

  def test_leftover_error(self):
    with self.assertRaises(AssertionError) as ctx:
      self.CheckWithErrors("x = 0  # attribute-error")
    self.assertIn("Errors not found", str(ctx.exception))

  def test_misspelled_leftover_error(self):
    with self.assertRaises(AssertionError) as ctx:
      self.CheckWithErrors("x = 0  # misspelled-error")
    self.assertIn("Errors not found", str(ctx.exception))

  def test_mismatched_regex(self):
    err = self.CheckWithErrors("(10).foo  # attribute-error[e]")
    with self.assertRaises(AssertionError) as ctx:
      self.assertErrorRegexes(err, {"e": r"does not match error message"})
    self.assertIn("Bad error message", str(ctx.exception))

  def test_missing_regex(self):
    err = self.CheckWithErrors("(10).foo  # attribute-error[e]")
    with self.assertRaises(AssertionError) as ctx:
      self.assertErrorRegexes(err, {})
    self.assertEqual(str(ctx.exception), "No regex for mark e")

  def test_leftover_regex(self):
    err = self.CheckWithErrors("x = 0")
    with self.assertRaises(AssertionError) as ctx:
      self.assertErrorRegexes(err, {"e": ""})
    self.assertEqual(str(ctx.exception), "Marks not found in code: e")

  def test_bad_check(self):
    with self.assertRaises(AssertionError) as ctx:
      self.Check("name_error  # name-error")
    self.assertIn("Cannot assert errors", str(ctx.exception))

  def test_bad_infer(self):
    with self.assertRaises(AssertionError) as ctx:
      self.Infer("name_error  # name-error")
    self.assertIn("Cannot assert errors", str(ctx.exception))

  def test_bad_infer_from_file(self):
    with file_utils.Tempdir() as d:
      d.create_file("some_file.py", "name_error  # name-error")
      with self.assertRaises(AssertionError) as ctx:
        self.InferFromFile(filename=d["some_file.py"], pythonpath=[])
    self.assertIn("Cannot assert errors", str(ctx.exception))


class SkipTest(test_base.TargetPython3FeatureTest):

  @test_utils.skipUnlessPy((3, 7), reason="testing skipUnlessPy")
  def test_skip_unless_py(self):
    # This test will fail if run in a version other than 3.7.
    self.Check("""
      import sys
      if sys.version_info.minor != 7:
        name_error
    """)

  @test_utils.skipIfPy((3, 7), reason="testing skipIfPy")
  def test_skip_if_py(self):
    # This test will fail if run in 3.7.
    self.Check("""
      import sys
      if sys.version_info.minor == 7:
        name_error
    """)

  @test_utils.skipBeforePy((3, 7), reason="testing skipBeforePy")
  def test_skip_before_py(self):
    # This will fail before 3.7.
    self.Check("""
      import sys
      if sys.version_info.minor < 7:
        name_error
    """)

  @test_utils.skipFromPy((3, 7), reason="testing skipFromPy")
  def test_skip_from_py(self):
    # This will fail in 3.7+.
    self.Check("""
      import sys
      if sys.version_info.minor >= 7:
        name_error
    """)


test_base.main(globals(), __name__ == "__main__")
