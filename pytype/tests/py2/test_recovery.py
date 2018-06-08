"""Tests for recovering after errors."""

from pytype.tests import test_base


class RecoveryTests(test_base.TargetPython27FeatureTest):
  """Tests for recovering after errors."""

  def testBadCall(self):
    ty = self.Infer("""
        def f():
          return "%s" % chr("foo")
      """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
        from typing import Union
        def f() -> Union[str, unicode]
    """)

  def testBadFunction(self):
    ty = self.Infer("""
      import time
      def f():
        return time.unknown_function(3)
      def g():
        return '%s' % f()
    """, report_errors=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      time = ...  # type: module
      def f() -> ?
      def g() -> Union[str, unicode]
    """)


test_base.main(globals(), __name__ == "__main__")
