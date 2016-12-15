"""Tests of __builtin__.tuple."""

import unittest


from pytype.tests import test_inference


class TupleTest(test_inference.InferenceTest):
  """Tests for __builtin__.tuple."""

  def testGetItemInt(self):
    ty = self.Infer("""\
      t = ("", 42)
      v1 = t[0]
      v2 = t[1]
      v3 = t[2]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      t = ...   # type: Tuple[str, int]
      v1 = ...  # type: str
      v2 = ...  # type: int
      v3 = ...  # type: str or int
    """)

  @unittest.skip("Needs better slice support in abstract.Tuple, convert.py.")
  def testGetItemSlice(self):
    ty = self.Infer("""\
      t = ("", 42)
      v1 = t[:]
      v2 = t[:1]
      v3 = t[1:]
      v4 = t[0:1]
      v5 = t[0:2:2]
      v6 = t[:][0]
    """)
    self.assertTypesMatchPytd(ty, """
      t = ...  # type: Tuple[str, int]
      v1 = ...  # type: Tuple[str, int]
      v2 = ...  # type: Tuple[str]
      v3 = ...  # type: Tuple[int]
      v4 = ...  # type: Tuple[str]
      v5 = ...  # type: Tuple[str]
      v6 = ...  # type: str
    """)

  def testUnpackTuple(self):
    ty = self.Infer("""\
      v1, v2 = ("", 42)
      v3, v4 = ("",)
      _, w = ("", 42)
      x, (y, z) = ("", (3.14, True))
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      v1 = ...  # type: str
      v2 = ...  # type: int
      v3 = ...  # type: str
      v4 = ...  # type: str
      _ = ...  # type: str
      w = ...  # type: int
      x = ...  # type: str
      y = ...  # type: float
      z = ...  # type: bool
    """)

  def testIteration(self):
    ty = self.Infer("""\
      class Foo(object):
        mytuple = (1, "foo", 3j)
        def __getitem__(self, pos):
          return Foo.mytuple.__getitem__(pos)
      r = [x for x in Foo()]
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        mytuple = ...  # type: Tuple[int, str, complex]
        def __getitem__(self, pos: int) -> int or str or complex
      x = ...  # type: int or str or complex
      r = ...  # type: List[int or str or complex]
    """)


if __name__ == "__main__":
  test_inference.main()
