"""Tests for our test framework."""

from pytype.tests import test_base
import six


class ErrorLogTest(test_base.TargetIndependentTest):

  def test_error_comments(self):
    err = self.CheckWithErrors("""\
      a = 10  # a random comment
      b = "hello"  # .mark
      c = a + b  # some-error
      d = a + b  # .another_mark
    """)
    six.assertCountEqual(self, err.marks.keys(), [".mark", ".another_mark"])
    self.assertEqual(err.marks[".mark"], 2)
    six.assertCountEqual(self, err.expected.keys(), [3])
    six.assertCountEqual(self, err.expected[3], "some-error")

  def test_error_matching(self):
    err = self.CheckWithErrors("""\
      a = 10
      b = "hello"
      c = a + b  # unsupported-operands
      d = a.foo()  # .mark
    """)
    self.assertErrorsMatch(err, [(".mark", "attribute-error", ".*foo.*")])


test_base.main(globals(), __name__ == "__main__")
