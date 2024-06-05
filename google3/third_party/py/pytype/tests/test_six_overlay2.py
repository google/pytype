"""Tests for methods in six_overlay.py."""

from pytype.tests import test_base


class SixTests(test_base.BaseTest):
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
      import six
      v = ...  # type: str
    """)

  def test_string_types(self):
    ty = self.Infer("""
      from typing import List, Union
      import six
      a = ''  # type: Union[str, List[str]]
      if isinstance(a, six.string_types):
        a = [a]
      b = ''  # type: str
      if isinstance(b, six.string_types):
        c = len(b)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      import six
      a: List[str]
      b: str
      c: int
    """)

  def test_integer_types(self):
    self.Check("""
      import six
      from typing import List, Union
      def foo(x: Union[List[int], int]) -> List[int]:
        if isinstance(x, six.integer_types):
          return [x]
        else:
          return x
    """)


if __name__ == "__main__":
  test_base.main()
