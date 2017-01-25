"""Tests of builtins (in pytd/builtins/__builtins__.pytd).

File 2/2. Split into two parts to enable better test parallelism.
"""


from pytype import utils
from pytype.tests import test_inference


class BuiltinTests2(test_inference.InferenceTest):
  """Tests for builtin methods and classes."""

  def testDivModWithUnknown(self):
    ty = self.Infer("""
      def f(x, y):
        divmod(x, __any_object__)
        return divmod(3, y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x: int or float or complex,
            y: int or float or complex) -> Tuple[int or float or complex, ...]
    """)

  def testDefaultDict(self):
    ty = self.Infer("""
      import collections
      r = collections.defaultdict()
      r[3] = 3
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      r = ...  # type: collections.defaultdict[int, int]
    """)

  def testDictUpdate(self):
    ty = self.Infer("""
      x = {}
      x.update(a=3, b=4)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: Dict[str, Any]
    """)

  def testImportLib(self):
    ty = self.Infer("""
      import importlib
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      importlib = ...  # type: module
    """)

  def testSetUnion(self):
    ty = self.Infer("""
      def f(y):
        return set.union(*y)
      def g(y):
        return set.intersection(*y)
      def h(y):
        return set.difference(*y)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(y) -> set: ...
      def g(y) -> set: ...
      def h(y) -> set: ...
    """)

  def testSetInit(self):
    ty = self.Infer("""
      data = set(x for x in [""])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      data = ...  # type: Set[str]
    """)

  def testFrozenSetInheritance(self):
    ty = self.Infer("""
      class Foo(frozenset):
        pass
      Foo([])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      class Foo(frozenset):
        pass
    """)

  def testOldStyleClass(self):
    ty = self.Infer("""
      class Foo:
        def get_dict(self):
          return self.__dict__
        def get_name(self):
          return self.__name__
        def get_class(self):
          return self.__class__
        def get_doc(self):
          return self.__doc__
        def get_module(self):
          return self.__module__
        def get_bases(self):
          return self.__bases__
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo:
        def get_dict(self) -> Dict[str, Any]
        def get_name(self) -> str
        def get_class(self) -> Type[Foo]
        def get_doc(self) -> str
        def get_module(self) -> str
        def get_bases(self) -> tuple
    """)

  def testNewStyleClass(self):
    ty = self.Infer("""
      class Foo(object):
        def get_dict(self):
          return self.__dict__
        def get_name(self):
          return self.__name__
        def get_class(self):
          return self.__class__
        def get_doc(self):
          return self.__doc__
        def get_module(self):
          return self.__module__
        def get_bases(self):
          return self.__bases__
        def get_hash(self):
          return self.__hash__()
        def get_mro(self):
          return self.__mro__
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        def get_dict(self) -> Dict[str, Any]
        def get_name(self) -> str
        def get_class(self) -> Type[Foo]
        def get_doc(self) -> str
        def get_module(self) -> str
        def get_hash(self) -> int
        def get_mro(self) -> list
        def get_bases(self) -> tuple
    """)

  def testDictInit(self):
    ty = self.Infer("""
      x = dict(u=3, v=4, w=5)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: dict
    """)

  def testDictIterators(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
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
      """, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        d = ...  # type: dict[str, int]
        key = ...  # type: str
        value = ...  # type: int
        item = ...  # type: Tuple[str, int]
      """)

  def testMax(self):
    ty = self.Infer("""
      x = dict(u=3, v=4, w=5)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: dict
    """)

  def testModule(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: module
      """)
      ty = self.Infer("""\
        import foo
        foo.x.bar()
        x = foo.__name__
        y = foo.x.baz
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        x = ...  # type: str
        y = ...  # type: Any
      """)

  def testClassMethod(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: classmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testStaticMethod(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: staticmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testMinMax(self):
    ty = self.Infer("""
      x = min(x for x in range(3))
      y = max(x for x in range(3))
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int
      y = ...  # type: int
    """)

  def testMap(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      lst3 = map(str, lst2)
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      x = ...  # type: Any
      lst3 = ...  # type: List[nothing]
    """)

  def testFromKeys(self):
    ty = self.Infer("""
      d1 = dict.fromkeys([1])
      d2 = dict.fromkeys([1], 0)
      d3 = dict.fromkeys("123")
      d4 = dict.fromkeys(bytearray("x"))
      d5 = dict.fromkeys(u"x")
      d6 = dict.fromkeys(iter("123"))
      d7 = dict.fromkeys({True: False})
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      d1 = ...  # type: Dict[int, None]
      d2 = ...  # type: Dict[int, int]
      d3 = ...  # type: Dict[str, None]
      d4 = ...  # type: Dict[int, None]
      d5 = ...  # type: Dict[unicode, None]
      d6 = ...  # type: Dict[str, None]
      d7 = ...  # type: Dict[bool, None]
    """)

  def testRedefinedBuiltin(self):
    ty = self.Infer("""
      class BaseException(Exception): pass
      class CryptoException(BaseException, ValueError): pass
    """)
    p1, p2 = ty.Lookup("CryptoException").parents
    self.assertEqual(p1.name, "BaseException")
    self.assertEqual(p2.name, "__builtin__.ValueError")
    self.assertTypesMatchPytd(ty, """
      class BaseException(Exception): ...
      class CryptoException(BaseException, ValueError): ...
    """)

  def testSum(self):
    ty = self.Infer("""
      x1 = sum([1, 2])
      x2 = sum([1, 2], 0)
      x3 = sum([1.0, 3j])
      x4 = sum([1.0, 3j], 0)
      x5 = sum([[1], ["2"]], [])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: int
      x2 = ...  # type: int
      x3 = ...  # type: int or float or complex
      x4 = ...  # type: int or float or complex
      x5 = ...  # type: List[int or str]
    """)

  def testReversed(self):
    ty, errors = self.InferAndCheck("""\
      x1 = reversed(xrange(42))
      x2 = reversed([42])
      x3 = reversed((4, 2))
      x4 = reversed("hello")
      x5 = reversed({42})
      x6 = reversed(frozenset([42]))
      x7 = reversed({True: 42})
    """)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: reversed[int]
      x2 = ...  # type: reversed[int]
      x3 = ...  # type: reversed[int]
      x4 = ...  # type: reversed[str]
      x5 = ...  # type: reversed[nothing]
      x6 = ...  # type: reversed[nothing]
      x7 = ...  # type: reversed[nothing]
    """)
    self.assertErrorLogIs(errors, [(5, "wrong-arg-types", r"Set\[int\]"),
                                   (6, "wrong-arg-types", r"FrozenSet\[int\]"),
                                   (7, "wrong-arg-types",
                                    r"Dict\[bool, int\]")])

  def testFilter(self):
    ty = self.Infer("""
      def f(x):
        pass
      x1 = filter(f, {1: None}.iterkeys())
      x2 = filter(None, {1: None}.iterkeys())
      x3 = filter(None, "")
      x4 = filter(None, u"")
      x5 = filter(None, bytearray(""))
      x6 = filter(None, (True, False))
      x7 = filter(None, {True, False})
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> None
      x1 = ...  # type: List[int]
      x2 = ...  # type: List[int]
      x3 = ...  # type: str
      x4 = ...  # type: unicode
      x5 = ...  # type: List[int]
      x6 = ...  # type: Tuple[bool, ...]
      x7 = ...  # type: List[bool]
    """)

  def testStrJoin(self):
    ty = self.Infer("""
      a = ",".join([])
      b = u",".join([])
      c = ",".join(["foo"])
      d = u",".join(["foo"])
      e = ",".join([u"foo"])
      f = u",".join([u"foo"])
      g = ",".join([u"foo", "bar"])
      h = u",".join([u"foo", "bar"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: str
      b = ...  # type: unicode
      c = ...  # type: str
      d = ...  # type: unicode
      e = ...  # type: unicode
      f = ...  # type: unicode
      g = ...  # type: str or unicode
      h = ...  # type: unicode
    """)

  def testBytearrayJoin(self):
    ty = self.Infer("""
      b = bytearray()
      x1 = b.join([])
      x2 = b.join(["x"])
      x3 = b.join([b])
    """)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bytearray
      x1 = ...  # type: bytearray
      x2 = ...  # type: bytearray
      x3 = ...  # type: bytearray
    """)

  def testReduce(self):
    self.assertNoErrors("""
      reduce(lambda x, y: x+y, [1,2,3]).real
      reduce(lambda x, y: x+y, ["foo"]).upper()
      reduce(lambda x, y: 4, "foo").real
      reduce(lambda x, y: 4, [], "foo").upper()
      reduce(lambda x, y: "s", [1,2,3], 0).upper()
    """)

  def testDictKeys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.viewkeys() & {1, 2, 3}
      b = m.viewkeys() - {1, 2, 3}
      c = m.viewkeys() | {1, 2, 3}
      d = m.viewkeys() ^ {1, 2, 3}
    """)
    self.assertTypesMatchPytd(ty, """
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[int or str]
      d = ...  # type: Set[int or str]
    """)

  def testDictPopItem(self):
    ty = self.Infer("""
      v = {"a": 1}.popitem()
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: Tuple[str, int]
    """)

  def testLong(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: long): ...
      """)
      self.assertNoErrors("""
        import foo
        foo.f(42)
      """, pythonpath=[d.path])

  def testLongConstant(self):
    ty = self.Infer("""
      MAX_VALUE = 2**64
    """)
    self.assertTypesMatchPytd(ty, """
      MAX_VALUE = ...  # type: int
    """)

  def testIter(self):
    ty = self.Infer("""
      x1 = iter("hello")
      x2 = iter(u"hello")
      x3 = iter(bytearray(42))
      x4 = iter(x for x in [42])
      x5 = iter([42])
      x6 = iter((42,))
      x7 = iter({42})
      x8 = iter({"a": 1})
      x9 = iter(int, 42)
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x1 = ...  # type: Iterator[str]
      x2 = ...  # type: Iterator[unicode]
      x3 = ...  # type: bytearray_iterator
      x4 = ...  # type: Generator[int, Any, Any]
      x5 = ...  # type: listiterator[int]
      x6 = ...  # type: tupleiterator[int]
      x7 = ...  # type: setiterator[int]
      x8 = ...  # type: `dictionary-keyiterator`[str]
      x9 = ...  # type: `callable-iterator`
    """)

  def testListInit(self):
    ty = self.Infer("""
      l1 = list()
      l2 = list([42])
      l3 = list({"a": 1}.iterkeys())
      l4 = list({"a": 1}.itervalues())
      l5 = list(iter([42]))
      l6 = list(reversed([42]))
      l7 = list(iter((42,)))
      l8 = list(iter({42}))
      l9 = list((42,))
      l10 = list({42})
      l11 = list("hello")
      l12 = list(iter(bytearray(42)))
      l13 = list(iter(xrange(42)))
      l14 = list(x for x in [42])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      l1 = ...  # type: List[nothing]
      l2 = ...  # type: List[int]
      l3 = ...  # type: List[str]
      l4 = ...  # type: List[int]
      l5 = ...  # type: List[int]
      l6 = ...  # type: List[int]
      l7 = ...  # type: List[int]
      l8 = ...  # type: List[int]
      l9 = ...  # type: List[int]
      l10 = ...  # type: List[int]
      l11 = ...  # type: List[str]
      l12 = ...  # type: List[int]
      l13 = ...  # type: List[int]
      l14 = ...  # type: List[int]
    """)

  def testTupleInit(self):
    ty = self.Infer("""
      t1 = tuple()
      t2 = tuple([42])
      t3 = tuple({"a": 1}.iterkeys())
      t4 = tuple({"a": 1}.itervalues())
      t5 = tuple(iter([42]))
      t6 = tuple(reversed([42]))
      t7 = tuple(iter((42,)))
      t8 = tuple(iter({42}))
      t9 = tuple((42,))
      t10 = tuple({42})
      t11 = tuple("hello")
      t12 = tuple(iter(bytearray(42)))
      t13 = tuple(iter(xrange(42)))
      t14 = tuple(x for x in [42])
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      t1 = ...  # type: Tuple[nothing, ...]
      t2 = ...  # type: Tuple[int, ...]
      t3 = ...  # type: Tuple[str, ...]
      t4 = ...  # type: Tuple[int, ...]
      t5 = ...  # type: Tuple[int, ...]
      t6 = ...  # type: Tuple[int, ...]
      t7 = ...  # type: Tuple[int, ...]
      t8 = ...  # type: Tuple[int, ...]
      t9 = ...  # type: Tuple[int, ...]
      t10 = ...  # type: Tuple[int, ...]
      t11 = ...  # type: Tuple[str, ...]
      t12 = ...  # type: Tuple[int, ...]
      t13 = ...  # type: Tuple[int, ...]
      t14 = ...  # type: Tuple[int, ...]
    """)

  def testEmptyTuple(self):
    self.assertNoErrors("""\
      isinstance(42, ())
      issubclass(int, ())
      type("X", (), {"foo": 42})
      type("X", (), {})
    """)

  def testListExtend(self):
    ty = self.Infer("""\
      x1 = [42]
      x1.extend([""])
      x2 = [42]
      x2.extend(("",))
      x3 = [42]
      x3.extend({""})
      x4 = [42]
      x4.extend(frozenset({""}))
    """)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: List[int or str]
      x2 = ...  # type: List[int or str]
      x3 = ...  # type: List[int or str]
      x4 = ...  # type: List[int or str]
    """)

  def testSorted(self):
    ty = self.Infer("""
      x1 = sorted("hello")
      x2 = sorted(u"hello")
      x3 = sorted(bytearray("hello"))
      x4 = sorted([])
      x5 = sorted([42], reversed=True)
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: List[str]
      x2 = ...  # type: List[unicode]
      x3 = ...  # type: List[int]
      x4 = ...  # type: List[nothing]
      x5 = ...  # type: List[int]
    """)

  def testEnumerate(self):
    ty = self.Infer("""
      x1 = enumerate([42])
      x2 = enumerate((42,))
      x3 = enumerate(x for x in range(5))
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: enumerate[int]
      x2 = ...  # type: enumerate[int]
      x3 = ...  # type: enumerate[int]
    """)

  def testFrozenSetInit(self):
    ty = self.Infer("""
      x1 = frozenset([42])
      x2 = frozenset({42})
      x3 = frozenset("hello")
    """, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: frozenset[int]
      x2 = ...  # type: frozenset[int]
      x3 = ...  # type: frozenset[str]
    """)

  def testFuncTools(self):
    self.assertNoErrors("""
      import functools
    """)

  def testABC(self):
    self.assertNoErrors("""
      import abc
    """)

  def testSetDefault(self):
    ty = self.Infer("""
      x = {}
      x['bar'] = 3
      y = x.setdefault('foo', 3.14)
      z = x['foo']
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: Dict[str, float or int]
      y = ...  # type: float or int
      z = ...  # type: float
    """)

  def testSetDefaultOneArg(self):
    ty = self.Infer("""
      x = {}
      x['bar'] = 3
      y = x.setdefault('foo')
      z = x['foo']
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: Dict[str, Optional[int]]
      y = ...  # type: Optional[int]
      z = ...  # type: None
    """)

  def testSetDefaultVarargs(self):
    ty = self.Infer("""\
      x1 = {}
      y1 = x1.setdefault(*("foo", 42))

      x2 = {}
      y2 = x2.setdefault(*["foo", 42])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any

      x1 = ...  # type: Dict[str, int]
      y1 = ...  # type: int

      x2 = ...  # type: dict
      y2 = ...  # type: Any
    """)

  def testSetDefaultError(self):
    ty, errors = self.InferAndCheck("""\
      x = {}
      y = x.setdefault()
      z = x.setdefault(1, 2, 3, *[])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      x = ...  # type: Dict[nothing, nothing]
      y = ...  # type: Any
      z = ...  # type: Any
    """)
    self.assertErrorLogIs(errors, [(2, "wrong-arg-count", "2.*0"),
                                   (3, "wrong-arg-count", "2.*3")])

  def testRedefineNext(self):
    ty = self.Infer("""
      next = 42
    """)
    self.assertTypesMatchPytd(ty, """
      next = ...  # type: int
    """)

  def testOsEnvironCopy(self):
    self.assertNoErrors("""
      import os
      os.environ.copy()["foo"] = "bar"
    """)

  def testPrintFunction(self):
    self.assertNoErrors("""
      from __future__ import print_function
      import sys
      print(file=sys.stderr)
    """)

  def testBytearrayInit(self):
    self.assertNoErrors("""
      bytearray(42)
      bytearray([42])
      bytearray(u"hello", "utf-8")
      bytearray(u"hello", "utf-8", "")
    """)

  def testCompile(self):
    self.assertNoErrors("""
      code = compile("1 + 2", "foo.py", "single")
    """)


if __name__ == "__main__":
  test_inference.main()
