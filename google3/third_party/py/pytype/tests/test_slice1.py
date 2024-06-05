"""Tests for slices."""

from pytype.tests import test_base


class SliceTest(test_base.BaseTest):
  """Tests for the SLICE_<n> opcodes, as well as for __getitem__(slice)."""

  def test_getslice(self):
    ty = self.Infer("""
      x = [1,2,3]
      a = x[:]
      b = x[1:]
      c = x[1:2]
      d = x[1:2:3]
      e = x[:2:3]
      f = x[1::3]
      g = x[1:2:]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x = ...  # type: List[int]
      a = ...  # type: List[int]
      b = ...  # type: List[int]
      c = ...  # type: List[int]
      d = ...  # type: List[int]
      e = ...  # type: List[int]
      f = ...  # type: List[int]
      g = ...  # type: List[int]
    """)

  def test_slice_getitem(self):
    self.Check("""
      class Foo:
        def __getitem__(self, s):
          return s
      assert_type(Foo()[:], slice)
    """)


if __name__ == "__main__":
  test_base.main()
