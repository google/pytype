"""Tests for slices."""

from pytype.tests import test_base


class SliceTest(test_base.BaseTest):
  """Tests for the SLICE_<n> opcodes, as well as for __getitem__(slice)."""

  def test_custom_getslice(self):
    ty = self.Infer("""
      class Foo:
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      _T0 = TypeVar('_T0')
      class Foo:
        def __getitem__(self, index: _T0) -> _T0: ...
      x: Foo
      a: slice
      b: slice
      c: slice
      d: slice
      e: slice
      f: slice
      g: slice
    """)


if __name__ == "__main__":
  test_base.main()
