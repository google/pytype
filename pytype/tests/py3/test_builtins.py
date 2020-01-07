"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd)."""

from pytype import file_utils
from pytype.tests import test_base


class BuiltinTests(test_base.TargetPython3BasicTest):
  """Tests for builtin methods and classes."""

  def testBoolReturnValue(self):
    ty = self.Infer("""
      def f():
        return True
      def g() -> bool:
        return f()
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> bool: ...
      def g() -> bool: ...
    """)

  def testSumReturn(self):
    self.Check("""
      from typing import List
      def f(x: List[float]) -> float:
        return sum(x)
    """)

  def testPrintFunction(self):
    self.Check("""
      from __future__ import print_function
      import sys
      print(file=sys.stderr)
    """)

  def testFilename(self):
    self.Check("""
      def foo(s: str) -> str:
        return s
      foo(__file__)
      """, filename="foobar.py")

  def testSuper(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Type
        def f(x: type): ...
        def g(x: Type[super]): ...
      """)
      ty = self.Infer("""
        from typing import Any, Type
        import foo
        def f(x): ...
        def g(x: object): ...
        def h(x: Any): ...
        def i(x: type): ...
        def j(x: Type[super]): ...
        f(super)
        g(super)
        h(super)
        i(super)
        j(super)
        foo.f(super)
        foo.g(super)
        v = super
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Type
        foo = ...  # type: module
        def f(x) -> None: ...
        def g(x: object) -> None: ...
        def h(x: Any) -> None: ...
        def i(x: type) -> None: ...
        def j(x: Type[super]) -> None: ...
        v = ...  # type: Type[super]
      """)

  def testBytearraySlice(self):
    self.Check("""
      def f(x: bytearray) -> bytearray:
        return x[1:]
      def g(x: bytearray) -> bytearray:
        return x[1:5:2]
    """)

  def testSetLength(self):
    self.Check("""
      from typing import Set
      x = ...  # type: Set[int]
      len(x)
      len(set())
    """)

  def testSequenceLength(self):
    self.Check("""
      from typing import Sequence
      x = ...  # type: Sequence
      len(x)
    """)

  def testMappingLength(self):
    self.Check("""
      from typing import Mapping
      x = ...  # type: Mapping
      len(x)
    """)


class BuiltinPython3FeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for builtin methods and classes."""

  def testBuiltins(self):
    self.Check("""
      import builtins
    """)

  def testUnicode(self):
    errors = self.CheckWithErrors("""\
      unicode("foo")
    """)
    self.assertErrorLogIs(errors, [(1, "name-error")])

  def testBytesIteration(self):
    errors = self.CheckWithErrors("""\
      def f():
        for x in bytes():
          return bytes() + x
    """)
    self.assertErrorLogIs(errors, [(3, "unsupported-operands")])

  def test_inplace_division(self):
    self.Check("""\
      x, y = 24, 3
      x /= y
      assert x == 8.0 and y == 3
      assert isinstance(x, float)
      x /= y
      assert x == (8.0/3.0) and y == 3
      assert isinstance(x, float)
    """)

  def test_removed_dict_methods(self):
    errors = self.CheckWithErrors("""\
      {}.iteritems
      {}.iterkeys
      {}.itervalues
      {}.viewitems
      {}.viewkeys
      {}.viewvalues
    """)
    self.assertErrorLogIs(
        errors, [(1, "attribute-error"), (2, "attribute-error"),
                 (3, "attribute-error"), (4, "attribute-error"),
                 (5, "attribute-error"), (6, "attribute-error")])

  def test_dict_views(self):
    self.Check("""
      from typing import KeysView, ItemsView, ValuesView
      def f(x: KeysView): ...
      def g(x: ItemsView): ...
      def h(x: ValuesView): ...
      f({}.keys())
      g({}.items())
      h({}.values())
    """)

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
      b = ...  # type: str
      d = ...  # type: str
      e = ...  # type: str
      f = ...  # type: str
      g = ...  # type: str
      h = ...  # type: str
    """)

  def testStrIsHashable(self):
    self.Check("""
      from typing import Any, Dict, Hashable
      def f(x: Dict[Hashable, Any]):
        return x["foo"]
      f({'foo': 1})
    """)

  def testBytearrayJoin(self):
    ty = self.Infer("""
      b = bytearray()
      x2 = b.join([b"x"])
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
      x = ...  # type: Iterator[str]
    """)

  def testIter1(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a = ...  # type: int
      b = ...  # type: int
      c = ...  # type: Union[int, str]
    """)

  def testFromKeys(self):
    ty = self.Infer("""
      d = dict.fromkeys(u"x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, None]
    """)

  def testDictKeys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.keys() & {1, 2, 3}
      b = m.keys() - {1, 2, 3}
      c = m.keys() | {1, 2, 3}
      d = m.keys() ^ {1, 2, 3}
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[int or str]
      d = ...  # type: Set[int or str]
    """)

  def testOpen(self):
    ty = self.Infer("""
      f1 = open("foo.py", "r")
      f2 = open("foo.pickled", "rb")
      v1 = f1.read()
      v2 = f2.read()
      def open_file(mode):
        f = open("foo.x", mode)
        return f, f.read()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import BinaryIO, IO, TextIO, Tuple, Union
      f1 = ...  # type: TextIO
      f2 = ...  # type: BinaryIO
      v1 = ...  # type: str
      v2 = ...  # type: bytes
      def open_file(mode) -> Tuple[IO[Union[bytes, str]], Union[bytes, str]]
    """)

  def testFilter(self):
    ty = self.Infer("""
      import re
      def f(x: int):
        pass
      x1 = filter(None, "")
      x2 = filter(None, bytearray(""))
      x3 = filter(None, (True, False))
      x4 = filter(None, {True, False})
      x5 = filter(f, {1: None}.keys())
      x6 = filter(None, {1: None}.keys())
      x7 = filter(re.compile("").search, ("",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      re: module
      def f(x: int) -> None
      x1 = ...  # type: Iterator[str]
      x2 = ...  # type: Iterator[int]
      x3 = ...  # type: Iterator[bool, ...]
      x4 = ...  # type: Iterator[bool]
      x5 = ...  # type: Iterator[int]
      x6 = ...  # type: Iterator[int]
      x7 = ...  # type: Iterator[str]
      """)

  def testSorted(self):
    ty = self.Infer("""
      x = sorted(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x = ...  # type: List[str]
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
      from typing import Iterator, Tuple, Union
      a = ...  # type: Iterator[Tuple[str, str]]
      b = ...  # type: Iterator[nothing]
      c = ...  # type: Iterator[Tuple[Union[int, complex]]]
      d = ...  # type: Iterator[nothing]
      e = ...  # type: Iterator[nothing]
      f = ...  # type: Iterator[Tuple[complex, int]]
      """)

  def testMapBasic(self):
    ty = self.Infer("""
      v = map(int, ("0",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      v = ...  # type: Iterator[int]
    """)

  def testMap(self):
    ty = self.Infer("""
      class Foo(object):
        pass

      def f():
        return map(lambda x: x, [Foo()])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      class Foo(object):
        pass

      def f() -> Iterator
    """)

  def testMap1(self):
    ty = self.Infer("""
      def f(input_string, sub):
        return ''.join(map(lambda ch: ch, input_string))
    """)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.str)

  def testMap2(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      lst3 = map(str, lst2)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Iterator
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      lst3 = ...  # type: Iterator[nothing]
    """)

  def testDict(self):
    ty = self.Infer("""
      def t_testDict():
        d = {}
        d['a'] = 3
        d[3j] = 1.0
        return _i1_(list(_i2_(d).values()))[0]
      def _i1_(x):
        return x
      def _i2_(x):
        return x
      t_testDict()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, List, Union
      def t_testDict() -> float or int
      # _i1_, _i2_ capture the more precise definitions of the ~dict, ~list
      # TODO(kramm): The float/int split happens because
      # InterpreterFunction.get_call_combinations uses deep_product_dict(). Do
      # we want the output in this form?
      def _i1_(x: List[float]) -> List[Union[float, int]]
      def _i2_(x: dict[complex or str, float or int]) -> Dict[complex or str, float or int]
    """)

  def testListInit(self):
    ty = self.Infer("""
      l3 = list({"a": 1}.keys())
      l4 = list({"a": 1}.values())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l3 = ...  # type: List[str]
      l4 = ...  # type: List[int]
    """)

  def testTupleInit(self):
    ty = self.Infer("""
      t3 = tuple({"a": 1}.keys())
      t4 = tuple({"a": 1}.values())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t3 = ...  # type: Tuple[str, ...]
      t4 = ...  # type: Tuple[int, ...]
    """)

  def testItems(self):
    ty = self.Infer("""
      lst = list({"a": 1}.items())
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
                                    r"Union\[bytes, str\].*int")])

  def testRemovedBuiltins(self):
    errors = self.CheckWithErrors("""\
      long
      {}.has_key
    """)
    self.assertErrorLogIs(errors, [(1, "name-error"), (2, "attribute-error")])

  def testRange(self):
    ty, errors = self.InferWithErrors("""\
      xrange(3)
      v = range(3)
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: range
    """)
    self.assertErrorLogIs(errors, [(1, "name-error")])

  def testCreateStr(self):
    self.Check("""
      str(b"foo", "utf-8")
    """)

  def testBytesConstant(self):
    ty = self.Infer("v = b'foo'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: bytes")

  def testUnicodeConstant(self):
    ty = self.Infer("v = 'foo\\u00e4'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: str")

  def testMemoryview(self):
    self.Check("""
      v = memoryview(b'abc')
      v.format
      v.itemsize
      v.shape
      v.strides
      v.suboffsets
      v.readonly
      v.ndim
      v[1]
      v[1:]
      98 in v
      [x for x in v]
      len(v)
      v[1] = 98
      v[1:] = b'bc'
    """)

  def testMemoryviewMethods(self):
    ty = self.Infer("""
      v1 = memoryview(b'abc')
      v2 = v1.tobytes()
      v3 = v1.tolist()
      v4 = v1.hex()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      v1 = ...  # type: memoryview
      v2 = ...  # type: bytes
      v3 = ...  # type: List[int]
      v4 = ...  # type: str
    """)

  def testMemoryviewContextmanager(self):
    ty = self.Infer("""
      with memoryview(b'abc') as v:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: memoryview
    """)

  def testArrayTobytes(self):
    ty = self.Infer("""
      import array
      def t_testTobytes():
        return array.array('B').tobytes()
    """)
    self.assertTypesMatchPytd(ty, """
      array = ...  # type: module
      def t_testTobytes() -> bytes
    """)

  def testIteratorBuiltins(self):
    ty = self.Infer("""
      v1 = map(int, ["0"])
      v2 = zip([0], [1])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator, Tuple
      v1 = ...  # type: Iterator[int]
      v2 = ...  # type: Iterator[Tuple[int, int]]
    """)

  def testNext(self):
    ty = self.Infer("""
      itr = iter((1, 2))
      v1 = itr.__next__()
      v2 = next(itr)
    """)
    self.assertTypesMatchPytd(ty, """
      itr = ...  # type: tupleiterator[int]
      v1 = ...  # type: int
      v2 = ...  # type: int
    """)

  def testAliasedError(self):
    # In Python 3, EnvironmentError and IOError became aliases for OSError.
    self.Check("""
      def f(e: OSError): ...
      def g(e: IOError): ...
      f(EnvironmentError())
      g(EnvironmentError())
    """)

  def testOSErrorSubclasses(self):
    # New in Python 3:
    self.Check("""
      BlockingIOError
      ChildProcessError
      ConnectionError
      FileExistsError
      FileNotFoundError
      InterruptedError
      IsADirectoryError
      NotADirectoryError
      PermissionError
      ProcessLookupError
      TimeoutError
    """)

  def testRawInput(self):
    # Removed in Python 3:
    errors = self.CheckWithErrors("raw_input")
    self.assertErrorLogIs(errors, [(1, "name-error")])

  def testClear(self):
    # new in Python 3
    self.Check("""
      bytearray().clear()
      [].clear()
    """)

  def testCopy(self):
    # new in python 3
    self.Check("""
      bytearray().copy()
      [].copy()
    """)

  def testRound(self):
    ty = self.Infer("""
      v1 = round(4.2)
      v2 = round(4.2, 1)
    """)
    self.assertTypesMatchPytd(ty, """
      v1: int
      v2: float
    """)

  def testIntBytesConversion(self):
    ty = self.Infer("""
      bytes_obj = (42).to_bytes(1, "little")
      int_obj = int.from_bytes(b"*", "little")
    """)
    self.assertTypesMatchPytd(ty, """
      bytes_obj: bytes
      int_obj: int
    """)

  def testUnicodeError(self):
    self.Check("""
      UnicodeDecodeError("", b"", 0, 0, "")
      UnicodeEncodeError("", u"", 0, 0, "")
    """)

  def testMinMax(self):
    ty = self.Infer("""
      x1 = min([1, 2, 3], default=3)
      x2 = min((), default='')
      y1 = max([1, 2, 3], default=3)
      y2 = max((), default='')
    """)
    # TODO(rechen): The types of x2 and y2 should be str, but we're not able to
    # type an optional argument as a typevar.
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x1 = ...  # type: int
      x2 = ...  # type: Any
      y1 = ...  # type: int
      y2 = ...  # type: Any
    """)


test_base.main(globals(), __name__ == "__main__")
