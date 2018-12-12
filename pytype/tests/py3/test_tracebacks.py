"""Tests for displaying tracebacks in error messages."""

from pytype.tests import test_base


class TracebackTest(test_base.TargetPython3BasicTest):
  """Tests for tracebacks in error messages."""

  def test_build_class(self):
    errors = self.CheckWithErrors("""\
      class Foo(object):
        def f(self, x: Bar):
          pass
    """)
    self.assertErrorLogIs(errors, [(2, "name-error", r"Bar.*not defined$")])


test_base.main(globals(), __name__ == "__main__")
