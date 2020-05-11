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

  def test_string_types(self):
    ty = self.Infer("""
      from typing import List, Text, Union
      import six
      a = ''  # type: Union[str, List[str]]
      if isinstance(a, six.string_types):
        a = [a]
      b = u''
      if isinstance(b, six.string_types):
        b = [b]
      c = ''  # type: Text
      if isinstance(c, six.string_types):
        d = len(c)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      six: module
      a: List[str]
      b: List[unicode]
      c: Union[str, unicode]
      d: int
    """)


test_base.main(globals(), __name__ == "__main__")
