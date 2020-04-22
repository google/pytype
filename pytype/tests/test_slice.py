"""Tests for slices."""

from pytype.tests import test_base


class SliceTest(test_base.TargetIndependentTest):
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
    """, deep=False)
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
    ty = self.Infer("""
      class Foo(object):
        def __getitem__(self, s):
          return s
      Foo()[:]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      class Foo(object):
        def __getitem__(self, s: slice) -> slice: ...
    """)


test_base.main(globals(), __name__ == "__main__")
