"""Tests of __builtin__.tuple."""

import unittest


from pytype import utils
from pytype.tests import test_base


class TupleTest(test_base.BaseTest):
  """Tests for __builtin__.tuple."""

  def testGetItemInt(self):
    ty = self.Infer("""\
      t = ("", 42)
      v1 = t[0]
      v2 = t[1]
      v3 = t[2]
      v4 = t[-1]
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t = ...   # type: Tuple[str, int]
      v1 = ...  # type: str
      v2 = ...  # type: int
      v3 = ...  # type: str or int
      v4 = ...  # type: int
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
    ty = self.Infer("""\
      v1, v2 = ("", 42)
      _, w = ("", 42)
      x, (y, z) = ("", (3.14, True))
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      v1 = ...  # type: str
      v2 = ...  # type: int
      _ = ...  # type: str
      w = ...  # type: int
      x = ...  # type: str
      y = ...  # type: float
      z = ...  # type: bool
    """)

  def testUnpackInlineTuple(self):
    ty = self.Infer("""\
      from __future__ import google_type_annotations
      from typing import Tuple
      def f(x: Tuple[str, int]):
        return x
      v1, v2 = f(__any_object__)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      def f(x: Tuple[str, int]) -> Tuple[str, int]: ...
      v1 = ...  # type: str
      v2 = ...  # type: int
    """)

  def testUnpackTupleOrTuple(self):
    self.Check("""
      from __future__ import google_type_annotations
      def f():
        if __random__:
          return (False, 'foo')
        else:
          return (False, 'foo')
      def g() -> str:
        a, b = f()
        return b
    """)

  def testUnpackTupleOrList(self):
    self.Check("""
      from __future__ import google_type_annotations
      def f():
        if __random__:
          return (False, 'foo')
        else:
          return ['foo', 'bar']
      def g() -> str:
        a, b = f()
        return b
    """)

  def testBadUnpacking(self):
    ty, errors = self.InferAndCheck("""\
      tup = (1, "")
      a, = tup
      b, c, d = tup
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      tup = ...  # type: Tuple[int, str]
      a = ...  # type: int or str
      b = ...  # type: int or str
      c = ...  # type: int or str
      d = ...  # type: int or str
    """)
    self.assertErrorLogIs(errors, [
        (2, "bad-unpacking", "2 values.*1 variable"),
        (3, "bad-unpacking", "2 values.*3 variables")])

  def testUnpackAmbiguousTuple(self):
    self.Check("""
      from __future__ import google_type_annotations
      def f() -> tuple:
        return __any_object__
      a, b = f()
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
      from typing import List, Tuple
      class Foo(object):
        mytuple = ...  # type: Tuple[int, str, complex]
        def __getitem__(self, pos: int) -> int or str or complex
      x = ...  # type: int or str or complex
      r = ...  # type: List[int or str or complex]
    """)

  def testTuplePrinting(self):
    _, errors = self.InferAndCheck("""\
      from __future__ import google_type_annotations
      from typing import Tuple
      def f(x: Tuple[str, ...]):
        pass
      def g(y: Tuple[str]):
        pass
      f((42,))
      f(tuple([42]))
      f(("", ""))  # okay
      g((42,))
      g(("", ""))
      g(("",))  # okay
      g(tuple([""]))  # okay
    """)
    x = r"Tuple\[str, \.\.\.\]"
    y = r"Tuple\[str\]"
    tuple_int = r"Tuple\[int\]"
    tuple_ints = r"Tuple\[int, \.\.\.\]"
    tuple_str_str = r"Tuple\[str, str\]"
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types",
                                    r"%s.*%s" % (x, tuple_int)),
                                   (8, "wrong-arg-types",
                                    r"%s.*%s" % (x, tuple_ints)),
                                   (10, "wrong-arg-types",
                                    r"%s.*%s" % (y, tuple_int)),
                                   (11, "wrong-arg-types",
                                    r"%s.*%s" % (y, tuple_str_str))
                                  ])

  def testInlineTuple(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[int, str]): ...
      """)
      self.Check("""
        from __future__ import google_type_annotations
        from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type((1, "")))
        g((1, ""))
        g(foo.A())
      """, pythonpath=[d.path])

  def testInlineTupleError(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        class A(Tuple[str, int]): ...
      """)
      _, errors = self.InferAndCheck("""\
        from __future__ import google_type_annotations
        from typing import Tuple, Type
        import foo
        def f(x: Type[Tuple[int, str]]):
          pass
        def g(x: Tuple[int, str]):
          pass
        f(type(("", 1)))
        g(("", 1))
        g(foo.A())
      """, pythonpath=[d.path])
      expected = r"Tuple\[int, str\]"
      actual = r"Tuple\[str, int\]"
      self.assertErrorLogIs(errors, [
          (8, "wrong-arg-types",
           r"Type\[%s\].*Type\[%s\]" % (expected, actual)),
          (9, "wrong-arg-types", r"%s.*%s" % (expected, actual)),
          (10, "wrong-arg-types", r"%s.*foo\.A" % expected)])

  def testTupleCombinationExplosion(self):
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Any, Dict, List, Tuple, Union
      AnyStr = Union[str, unicode]
      def f(x: Dict[AnyStr, Any]) -> List[Tuple]:
        return sorted((k, v) for k, v in x.iteritems() if k in {})
    """)

  def testMutableItem(self):
    ty = self.Infer("""
      v = {}
      w = v.setdefault("", ([], []))
      w[1].append(42)
      u = w[2]
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: dict[str, tuple[list[nothing], list[int]]]
      w = ...  # type: tuple[list[nothing], list[int]]
      u = ...  # type: list[int]
    """)

  def testBadTupleClassGetItem(self):
    _, errors = self.InferAndCheck("""\
      v = type((3, ""))
      w = v[0]
    """)
    self.assertErrorLogIs(errors, [(2, "not-indexable", r"tuple")])

  def testTupleInContainer(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      from typing import List, Tuple
      def f(l: List[Tuple[int, AnyStr]]):
        line, foo = l[0]
        return foo
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, TypeVar, Union
      AnyStr = TypeVar('AnyStr', str, unicode)
      def f(l: List[Tuple[int, AnyStr]]) -> Union[str, unicode]: ...
    """)

  def testTupleIsInstance(self):
    ty = self.Infer("""
      x = ()
      if isinstance(x, tuple):
        y = 42
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      x = ...  # type: Tuple[nothing, ...]
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
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple, Union
      a = ...  # type: Tuple[int, ...]
      b = ...  # type: Tuple[Union[int, str], ...]
    """)


if __name__ == "__main__":
  test_base.main()
