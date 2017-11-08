"""Tests for __builtin__.list."""

from pytype.tests import test_base


class ListTest(test_base.BaseTest):
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

  def test_inplace_mutates(self):
    ty = self.Infer("""
      a = []
      b = a
      a += [42]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[int]
      b = ...  # type: List[int]
    """)

  def test_add_string(self):
    ty = self.Infer("""
      a = []
      a += "foo"
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      a = ...  # type: List[str]
    """)


if __name__ == "__main__":
  test_base.main()
