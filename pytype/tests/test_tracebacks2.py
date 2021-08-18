"""Tests for displaying tracebacks in error messages."""

from pytype.tests import test_base


class TracebackTest(test_base.BaseTest):
  """Tests for tracebacks in error messages."""

  def test_build_class(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def f(self, x: Bar):  # name-error[e]
          pass
    """)
    self.assertErrorRegexes(errors, {"e": r"Bar.*not defined$"})


if __name__ == "__main__":
  test_base.main()
