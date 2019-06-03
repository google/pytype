"""Tests for methods in six_overlay.py."""

from pytype.tests import test_base


class SixTests(test_base.TargetPython3FeatureTest):
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
      v = ...  # type: str
    """)

  def test_string_types(self):
    ty = self.Infer("""
      from typing import List, Text, Union
      import six
      a = ''  # type: Union[str, List[str]]
      if isinstance(a, six.string_types):
        a = [a]
      b = ''  # type: Text
      if isinstance(b, six.string_types):
        b = len(b)
    """)
    self.assertTypesMatchPytd(
        ty, """
      from typing import List
      six: module = ...
      a: List[str] = ...
      b: int = ...
    """)


test_base.main(globals(), __name__ == "__main__")
