"""Tests for slices."""

from pytype.tests import test_base


class SliceTest(test_base.TargetPython27FeatureTest):
  """Tests for the SLICE_<n> opcodes, as well as for __getitem__(slice)."""

  def test_custom_getslice(self):
    ty = self.Infer("""
      class Foo(object):
        def __getslice__(self, i, j):
          return (i, j)
        def __getitem__(self, index):
          return index
      x = Foo()
      a = x[:]
      b = x[1:]
      c = x[1:2]
      d = x[1:2:3]
      e = x[:2:3]
      f = x[1::3]
      g = x[1:2:]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      class Foo(object):
        def __getslice__(self, i:int, j:int) -> Tuple[int, int]: ...
        def __getitem__(self, index: slice) -> slice: ...
      x = ...  # type: Foo
      a = ...  # type: Tuple[int, int]
      b = ...  # type: Tuple[int, int]
      c = ...  # type: Tuple[int, int]
      d = ...  # type: slice
      e = ...  # type: slice
      f = ...  # type: slice
      g = ...  # type: slice
    """)


test_base.main(globals(), __name__ == "__main__")
