"""Tests for __builtin__.list."""

from pytype.tests import test_inference


class ListTest(test_inference.InferenceTest):
  """Tests for __builtin__.list."""

  def test_add(self):
    ty = self.Infer("""
      a = []
      a = a + [42]
      b = []
      b = b + [42]
      b = b + ["foo"]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[Union[int, str]]
    """)

  def test_inplace_add(self):
    ty = self.Infer("""
      a = []
      a += [42]
      b = []
      b += [42]
      b += ["foo"]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[Union[int, str]]
    """)


if __name__ == "__main__":
  test_inference.main()
