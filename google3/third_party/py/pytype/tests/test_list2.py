"""Tests for builtins.list."""

from pytype.tests import test_base


class ListTestBasic(test_base.BaseTest):
  """Basic tests for builtins.list in Python 3."""

  def test_repeated_add(self):
    # At the time of this writing, this test completes in <5s. If it takes
    # significantly longer, there's been a performance regression.
    self.CheckWithErrors("""
      from typing import List, Text, Tuple
      def f() -> Tuple[List[Text]]:
        x = (
            ['' % __any_object__, ''] + [''] + [''] + [''.format()] + [''] +
            [['' % __any_object__, '', '']]
        )
        return ([__any_object__] + [''] + x,)  # bad-return-type
    """)

  def test_bad_comprehension(self):
    self.CheckWithErrors("""
      x = None
      l = [y for y in x]  # attribute-error
    """)


class ListTest(test_base.BaseTest):
  """Tests for builtins.list in Python 3."""

  def test_byte_unpack_ex(self):
    ty = self.Infer("""
      from typing import List
      a, *b, c, d = 1, 2, 3, 4, 5, 6, 7
      i, *j = 1, 2, 3, "4"
      *k, l = 4, 5, 6
      m, *n, o = [4, 5, "6", None, 7, 8]
      p, *q, r = 4, 5, "6", None, 7, 8
      vars = None # type : List[int]
      s, *t, u = vars
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Optional, Union
      a = ... # type: int
      b = ... # type: List[int]
      c = ... # type: int
      d = ... # type: int
      i = ... # type: int
      j = ... # type: List[Union[int, str]]
      k = ... # type: List[int]
      l = ... # type: int
      m = ... # type: int
      n = ... # type: List[Optional[Union[int, str]]]
      o = ... # type: int
      p = ... # type: int
      q = ... # type: List[Optional[Union[int, str]]]
      r = ... # type: int
      s = ...  # type: int
      t = ...  # type: List[int]
      u = ...  # type: int
      vars = ...  # type: List[int]
    """)

  def test_getitem_slot(self):
    ty, _ = self.InferWithErrors("""
      a = [1, '2', 3, 4]
      p = a[1]
      q = 1 if __random__ else 2
      r = a[q]
      s = a["s"]  # unsupported-operands
      t = a[-1]
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      p = ...  # type: str
      q = ...  # type: int
      r = ...  # type: Union[int, str]
      s = ...  # type: Any
      t = ...  # type: int
      """)

  def test_slice_returntype(self):
    # each of the superclasses of list should return their own type when sliced.
    ty, _ = self.InferWithErrors("""
      from typing import Sequence, MutableSequence
      a: Sequence[int] = [1]
      b = a[0:1]
      c: MutableSequence[int] = [1]
      d = c[0:1]
      e = [2]
      f = e[0:1]
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, MutableSequence, Sequence
      a = ...  # type: Sequence[int]
      b = ...  # type: Sequence[int]
      c = ...  # type: MutableSequence[int]
      d = ...  # type: MutableSequence[int]
      e = ...  # type: List[int]
      f = ...  # type: List[int]
      """)

  @test_base.skip("Requires more precise slice objects")
  def test_getitem_slice(self):
    # Python 3 uses __getitem__ with slice objects instead of __getslice__.
    # Pytype doesn't support slice objects well, so a lot of results here are
    # imprecise. It also means wrong-arg-types won't be detected.
    ty, _ = self.InferWithErrors("""
      a = [1, '2', 3, 4]
      b = a[:]
      c = 1 if __random__ else 2
      d = a[c:2]
      e = a[c:]
      f = a[2:]
      g = a[2:None]
      h = a[None:2]
      i = a[None:None]
      j = a[int:str]  # wrong-arg-types
      k = a["s":]  # wrong-arg-types
      m = a[1:-1]
      n = a[0:0]
      o = a[1:1]
      p = a[1:2]
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Union
      a = ...  # type: List[Union[int, str]]
      b = ...  # type: List[Union[int, str]]
      c = ...  # type: int
      d = ...  # type: List[str]
      e = ...  # type: List[Union[int, str]]
      f = ...  # type: List[int]
      g = ...  # type: List[int]
      h = ...  # type: List[Union[int, str]]
      i = ...  # type: List[Union[int, str]]
      j = ...  # type: Any
      k = ...  # type: Any
      m = ...  # type: List[Union[int, str]]
      n = ...  # type: List[nothing]
      o = ...  # type: List[nothing]
      p = ...  # type: List[str]
      """)

  def test_appends(self):
    # Regression test for a crash involving list appends and accesses for a
    # variable with multiple bindings.
    self.Check("""
    from typing import List
    def f():
      lst1: List[List[str]] = []
      lst2: List[List[str]] = []
      if __random__:
        x, lst1 = __any_object__
      else:
        x = lst2[-1]
      lst1.append(x)
      lst2.append(lst1[-1])
    """)

  def test_clear(self):
    ty = self.Infer("""
      a = [0]
      a.clear()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      a = ...  # type: List[int]
    """)


if __name__ == "__main__":
  test_base.main()
