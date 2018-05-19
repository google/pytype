"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd)."""

from pytype import utils
from pytype.tests import test_base


class BuiltinTests(test_base.TargetPython27FeatureTest):
  """Tests for builtin methods and classes."""

  def testLong(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: long): ...
      """)
      self.Check("""
        import foo
        foo.f(42)
      """, pythonpath=[d.path])

  def testStrJoin(self):
    ty = self.Infer("""
      b = u",".join([])
      d = u",".join(["foo"])
      e = ",".join([u"foo"])
      f = u",".join([u"foo"])
      g = ",".join([u"foo", "bar"])
      h = u",".join([u"foo", "bar"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: unicode
      d = ...  # type: unicode
      e = ...  # type: unicode
      f = ...  # type: unicode
      g = ...  # type: str or unicode
      h = ...  # type: unicode
    """)

  def testBytearrayJoin(self):
    ty = self.Infer("""
      b = bytearray()
      x2 = b.join(["x"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bytearray
      x2 = ...  # type: bytearray
    """)

  def testIter(self):
    ty = self.Infer("""
      x = iter(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      x = ...  # type: Iterator[unicode]
    """)

  def testFromKeys(self):
    ty = self.Infer("""
      d = dict.fromkeys(u"x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[unicode, None]
    """)

  def testDictIterators(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Iterator
        def need_iterator(x: Iterator[Any]) -> None: ...
      """)
      ty = self.Infer("""\
        import foo
        d = {"a": 1}
        foo.need_iterator(d.iterkeys())
        key = d.iterkeys().next()
        foo.need_iterator(d.itervalues())
        value = d.itervalues().next()
        foo.need_iterator(d.iteritems())
        item = d.iteritems().next()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Dict, Tuple
        foo = ...  # type: module
        d = ...  # type: Dict[str, int]
        key = ...  # type: str
        value = ...  # type: int
        item = ...  # type: Tuple[str, int]
      """)

  def testDictKeys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.viewkeys() & {1, 2, 3}
      b = m.viewkeys() - {1, 2, 3}
      c = m.viewkeys() | {1, 2, 3}
      d = m.viewkeys() ^ {1, 2, 3}
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[int or str]
      d = ...  # type: Set[int or str]
    """)

  # TODO(sivachandra): Move this to a target independent test after
  # b/78373730 is fixed.
  def testSetDefaultError(self):
    ty, errors = self.InferWithErrors("""\
      x = {}
      y = x.setdefault()
      z = x.setdefault(1, 2, 3, *[])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      x = ...  # type: Dict[nothing, nothing]
      y = ...  # type: Any
      z = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-count", "2.*0"),
                                   (3, "wrong-arg-count", "2.*3")])

  def testFilter(self):
    ty = self.Infer("""
      x1 = filter(None, {1: None}.iterkeys())
      x2 = filter(None, u"")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[int]
      x2 = ...  # type: unicode
    """)

  def testSorted(self):
    ty = self.Infer("""
      x = sorted(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x = ...  # type: List[unicode]
    """)

  def testZip(self):
    ty = self.Infer("""
      a = zip("foo", u"bar")
      b = zip(())
      c = zip((1, 2j))
      d = zip((1, 2, 3), ())
      e = zip((), (1, 2, 3))
      f = zip((1j, 2j), (1, 2))
      assert zip([], [], [])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple, Union
      a = ...  # type: List[Tuple[str, unicode]]
      b = ...  # type: List[nothing]
      c = ...  # type: List[Tuple[Union[int, complex]]]
      d = ...  # type: List[nothing]
      e = ...  # type: List[nothing]
      f = ...  # type: List[Tuple[complex, int]]
      """)

  def testOsOpen(self):
    ty = self.Infer("""
      import os
      def f():
        return open("/dev/null")
      def g():
        return os.open("/dev/null", os.O_RDONLY, 0777)
    """)
    self.assertTypesMatchPytd(ty, """
      os = ...  # type: module

      def f() -> file
      def g() -> int
    """)

  # TODO(sivachandra): Move this to a target independent test after
  # b/78373730 is fixed.
  def testTuple2(self):
    ty = self.Infer("""
      def f(x, y):
        return y
      def g():
        args = (4, )
        return f(3, *args)
      g()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _T1 = TypeVar("_T1")
      def f(x, y: _T1) -> _T1: ...
      def g() -> int: ...
    """)

  def testMapBasic(self):
    ty = self.Infer("""
      v = map(int, ("0",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      v = ...  # type: List[int]
    """)

  def testMap(self):
    ty = self.Infer("""
      class Foo(object):
        pass

      def f():
        return map(lambda x: x, [Foo()])
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        pass

      def f() -> list
    """)

  def testMap1(self):
    ty = self.Infer("""
      def f(input_string, sub):
        return ''.join(map(lambda ch: ch, input_string))
    """)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.anything)

  def testMap2(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      lst3 = map(str, lst2)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      x = ...  # type: Any
      lst3 = ...  # type: List[nothing]
    """)

  def testDict(self):
    ty = self.Infer("""
      def t_testDict():
        d = {}
        d['a'] = 3
        d[3j] = 1.0
        return _i1_(_i2_(d).values())[0]
      def _i1_(x):
        return x
      def _i2_(x):
        return x
      t_testDict()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List
      def t_testDict() -> float or int
      # _i1_, _i2_ capture the more precise definitions of the ~dict, ~list
      # TODO(kramm): The float/int split happens because
      # InterpreterFunction.get_call_combinations uses deep_product_dict(). Do
      # we want the output in this form?
      def _i1_(x: List[float]) -> List[float]
      def _i1_(x: List[int]) -> List[int]
      def _i2_(x: dict[complex or str, float or int]) -> Dict[complex or str, float or int]
    """)

  def testListInit(self):
    ty = self.Infer("""
      l3 = list({"a": 1}.iterkeys())
      l4 = list({"a": 1}.itervalues())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l3 = ...  # type: List[str]
      l4 = ...  # type: List[int]
    """)

  def testTupleInit(self):
    ty = self.Infer("""
      t3 = tuple({"a": 1}.iterkeys())
      t4 = tuple({"a": 1}.itervalues())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t3 = ...  # type: Tuple[str, ...]
      t4 = ...  # type: Tuple[int, ...]
    """)

  def testSequenceLength(self):
    self.Check("""
      len(buffer(""))
    """)

  def testExceptionMessage(self):
    ty = self.Infer("""
      class MyException(Exception):
        def get_message(self):
          return self.message
    """)
    self.assertTypesMatchPytd(ty, """
      class MyException(Exception):
        def get_message(self) -> str
    """)

  def testIterItems(self):
    ty = self.Infer("""
      lst = list({"a": 1}.iteritems())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      lst = ...  # type: List[Tuple[str, int]]
    """)

  def testIntInit(self):
    _, errors = self.InferWithErrors("""\
      int(0, 1)  # line 8: expected str or unicode, got int for first arg
    """)
    self.assertErrorLogIs(errors, [(1, "wrong-arg-types",
                                    r"Union\[str, unicode\].*int")])

  def testAddStrAndBytearray(self):
    ty = self.Infer("""
      v = "abc" + bytearray()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: bytearray
    """)

  def testBytearraySetItem(self):
    self.Check("""
      ba = bytearray("hello")
      ba[0] = "j"
      ba[4:] = buffer("yfish")
    """)

  def testNext(self):
    ty = self.Infer("""
      itr = iter((1, 2))
      v1 = itr.next()
      v2 = next(itr)
    """)
    self.assertTypesMatchPytd(ty, """
      itr = ...  # type: tupleiterator[int]
      v1 = ...  # type: int
      v2 = ...  # type: int
    """)

  def testStrUnicodeMod(self):
    ty = self.Infer("""
        def t_testStrUnicodeMod():
          a = u"Hello"
          return "%s Uni" %(u"Hello")
        t_testStrUnicodeMod()
      """, deep=False)
    self.assertTypesMatchPytd(ty, """
        def t_testStrUnicodeMod() -> unicode
      """)

test_base.main(globals(), __name__ == "__main__")
