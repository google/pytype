"""Tests for our test framework."""

from pytype.tests import test_base


class ErrorLogTest(test_base.TargetIndependentTest):

  def test_error_comments(self):
    err = self.CheckWithErrors("""\
      a = 10  # a random comment
      b = "hello"  # .mark
      c = a + b  # some-error
      d = a + b  # .another_mark
    """)
    self.assertCountEqual(err.marks.keys(), [".mark", ".another_mark"])
    self.assertEqual(err.marks[".mark"], 2)
    self.assertCountEqual(err.expected.keys(), [3])
    self.assertCountEqual(err.expected[3], "some-error")

  def test_error_matching(self):
    err = self.CheckWithErrors("""\
      a = 10
      b = "hello"
      c = a + b  # unsupported-operands
      d = a.foo()  # .mark
    """)
    self.assertErrorsMatch(err, [(".mark", "attribute-error", ".*foo.*")])


test_base.main(globals(), __name__ == "__main__")
