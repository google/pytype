"""Tests for methods in six_overlay.py."""

from pytype.tests import test_base


class SixTests(test_base.TargetPython27FeatureTest):
  """Tests for six and six_overlay."""

  def test_version_check(self):
    ty = self.Infer("""
      import six
      if six.PY2:
        v = 42
      elif six.PY3:
        v = "hello world"
      else:
        v = None
    """)
    self.assertTypesMatchPytd(ty, """
      six = ...  # type: module
      v = ...  # type: int
    """)


test_base.main(globals(), __name__ == "__main__")
