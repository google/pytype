"""Tests for the error format itself."""

from pytype.tests import test_base


class ErrorTest(test_base.BaseTest):
  """Tests for errors."""

  def test_error_format(self):
    _, errors = self.InferWithErrors("""
      def f(x):
        y = 42
        y.foobar  # attribute-error[e]
    """)
    self.assertDiagnosticRegexes(
        errors,
        {
            "e": (
                r"dummy_input_file:3:3:"
                r" \x1b\[1m\x1b\[31merror\x1b\[39m\x1b\[0m: in f: No attribute"
                r" 'foobar' on int \[attribute-error\]"
            )
        },
    )

  # TODO: b/338455486 - Add a test case for diagnostic missing a filepath
  # information


if __name__ == "__main__":
  test_base.main()
