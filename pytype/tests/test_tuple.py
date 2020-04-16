"""Tests of __builtin__.tuple."""

from pytype.tests import test_base


class TupleTest(test_base.TargetIndependentTest):
  """Tests for __builtin__.tuple."""

  def testGetItemInt(self):
    ty = self.Infer("""
      t = ("", 42)
      v1 = t[0]
      v2 = t[1]
      v3 = t[2]
      v4 = t[-1]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t = ...   # type: Tuple[str, int]
      v1 = ...  # type: str
      v2 = ...  # type: int
      v3 = ...  # type: str or int
      v4 = ...  # type: int
    """)

  @test_base.skip("Needs better slice support in abstract.Tuple, convert.py.")
  def testGetItemSlice(self):
    ty = self.Infer("""
      t = ("", 42)
      v1 = t[:]
      v2 = t[:1]
      v3 = t[1:]
      v4 = t[0:1]
      v5 = t[0:2:2]
      v6 = t[:][0]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t = ...  # type: Tuple[str, int]
      v1 = ...  # type: Tuple[str, int]
      v2 = ...  # type: Tuple[str]
      v3 = ...  # type: Tuple[int]
      v4 = ...  # type: Tuple[str]
      v5 = ...  # type: Tuple[str]
      v6 = ...  # type: str
    """)

  def testUnpackTuple(self):
    ty = self.Infer("""
      v1, v2 = ("", 42)
      _, w = ("", 42)
      x, (y, z) = ("", (3.14, True))
    """)
    self.assertTypesMatchPytd(ty, """
      v1 = ...  # type: str
      v2 = ...  # type: int
      _ = ...  # type: str
      w = ...  # type: int
      x = ...  # type: str
      y = ...  # type: float
      z = ...  # type: bool
    """)

  def testBadUnpacking(self):
    ty, errors = self.InferWithErrors("""
      tup = (1, "")
      a, = tup  # bad-unpacking[e1]
      b, c, d = tup  # bad-unpacking[e2]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      tup = ...  # type: Tuple[int, str]
      a = ...  # type: int or str
      b = ...  # type: int or str
      c = ...  # type: int or str
      d = ...  # type: int or str
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"2 values.*1 variable", "e2": r"2 values.*3 variables"})

  def testMutableItem(self):
    ty = self.Infer("""
      v = {}
      w = v.setdefault("", ([], []))
      w[1].append(42)
      u = w[2]
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: dict[str, tuple[list[nothing], list[int]]]
      w = ...  # type: tuple[list[nothing], list[int]]
      u = ...  # type: list[int]
    """)

  def testBadTupleClassGetItem(self):
    _, errors = self.InferWithErrors("""
      v = type((3, ""))
      w = v[0]  # not-indexable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"tuple"})

  def testTupleIsInstance(self):
    ty = self.Infer("""
      x = ()
      if isinstance(x, tuple):
        y = 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      x = ...  # type: Tuple[()]
      y = ...  # type: int
    """)

  def testAddTwice(self):
    self.Check("() + () + ()")

  def testInplaceAdd(self):
    ty = self.Infer("""
      a = ()
      a += (42,)
      b = ()
      b += (42,)
      b += ("foo",)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      a = ...  # type: Tuple[int, ...]
      b = ...  # type: Tuple[Union[int, str], ...]
    """)

  def testTupleOfTuple(self):
    self.assertNoCrash(self.Infer, """
      def f(x=()):
        x = (x,)
        enumerate(x)
        lambda: x
        return x
    """)


test_base.main(globals(), __name__ == "__main__")
