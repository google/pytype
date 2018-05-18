"""Tests for control flow (with statements, loops, exceptions, etc.)."""

from pytype.tests import test_base


class FlowTest(test_base.TargetPython27FeatureTest):
  """Tests for control flow.

  These tests primarily test instruction ordering and CFG traversal of the
  bytecode interpreter, i.e., their primary focus isn't the inferred types.
  Even though they check the validity of the latter, they're mostly smoke tests.
  """

  # py2 `except x, y` syntax

  def test_exception(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_two_except_handlers(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
        except:
          return 3.5
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)


test_base.main(globals(), __name__ == "__main__")
