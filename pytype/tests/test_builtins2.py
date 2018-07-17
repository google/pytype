"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd).

File 2/3. Split into parts to enable better test parallelism.
"""

from pytype import file_utils
from pytype.tests import test_base


class BuiltinTests2(test_base.TargetIndependentTest):
  """Tests for builtin methods and classes."""

  def testDivModWithUnknown(self):
    ty = self.Infer("""
      def f(x, y):
        divmod(x, __any_object__)
        return divmod(3, y)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Tuple
      def f(x, y) -> Tuple[Any, Any]
    """)

  def testDefaultDict(self):
    ty = self.Infer("""
      import collections
      r = collections.defaultdict()
      r[3] = 3
    """)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      r = ...  # type: collections.defaultdict[int, int]
    """)

  def testDictUpdate(self):
    ty = self.Infer("""
      x = {}
      x.update(a=3, b=4)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict
      x = ...  # type: Dict[str, int]
    """)

  def testImportLib(self):
    ty = self.Infer("""
      import importlib
    """)
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
    """)
    self.assertTypesMatchPytd(ty, """
      def f(y) -> set: ...
      def g(y) -> set: ...
      def h(y) -> set: ...
    """)

  def testSetInit(self):
    ty = self.Infer("""
      data = set(x for x in [""])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Set
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Type
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
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict, Type
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
      x1 = dict(u=3, v=4, w=5)
      x2 = dict([(3, "")])
      x3 = dict(((3, ""),))
      x4 = dict({(3, "")})
      x5 = dict({})
      x6 = dict({3: ""})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      x1 = ...  # type: dict
      x2 = ...  # type: Dict[int, str]
      x3 = ...  # type: Dict[int, str]
      x4 = ...  # type: Dict[int, str]
      x5 = ...  # type: Dict[nothing, nothing]
      x6 = ...  # type: Dict[int, str]
    """)

  def testMax(self):
    ty = self.Infer("""
      x = dict(u=3, v=4, w=5)
    """)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: dict
    """)

  def testModule(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = ...  # type: module
      """)
      ty = self.Infer("""\
        import foo
        foo.x.bar()
        x = foo.__name__
        y = foo.x.baz
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        x = ...  # type: str
        y = ...  # type: Any
      """)

  def testClassMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: classmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Type
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testStaticMethod(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class A(object):
          x = ...  # type: staticmethod
      """)
      ty = self.Infer("""\
        from foo import A
        y = A.x()
        z = A().x()
      """, deep=False, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Type
        A = ...  # type: Type[foo.A]
        y = ...  # type: Any
        z = ...  # type: Any
      """)

  def testMinMax(self):
    ty = self.Infer("""
      x1 = min(x for x in range(3))
      x2 = min([3.1, 4.1], key=lambda n: n)
      x3 = min((1, 2, 3), key=int)
      y1 = max(x for x in range(3))
      y2 = max([3.1, 4.1], key=lambda n: n)
      y3 = max((1, 2, 3), key=int)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: int
      x2 = ...  # type: float
      x3 = ...  # type: int
      y1 = ...  # type: int
      y2 = ...  # type: float
      y3 = ...  # type: int
    """)

  def testMaxDifferentTypes(self):
    ty = self.Infer("""
      a = max(1, None)
      b = max(1, None, 3j)
      c = max(1, None, 3j, "str")
      d = max(1, 2, 3, 4, 5, 6, 7)
      e = max(1, None, key=int)
      f = max(1, None, 3j, key=int)
      g = max(1, None, 3j, "str", key=int)
      h = max(1, 2, 3, 4, 5, 6, 7, key=int)
      i = max([1,2,3,4])
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      a = ...  # type: Optional[int]
      b = ...  # type: Optional[Union[complex, int]]
      c = ...  # type: Optional[Union[complex, int, str]]
      d = ...  # type: int
      e = ...  # type: Optional[int]
      f = ...  # type: Optional[Union[complex, int]]
      g = ...  # type: Optional[Union[complex, int, str]]
      h = ...  # type: int
      i = ...  # type: int
      """)

  def testMinDifferentTypes(self):
    ty = self.Infer("""
      a = min(1, None)
      b = min(1, None, 3j)
      c = min(1, None, 3j, "str")
      d = min(1, 2, 3, 4, 5, 6, 7)
      e = min(1, None, key=int)
      f = min(1, None, 3j, key=int)
      g = min(1, None, 3j, "str", key=int)
      h = min(1, 2, 3, 4, 5, 6, 7, key=int)
      i = min([1,2,3,4])
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Optional, Union
      a = ...  # type: Optional[int]
      b = ...  # type: Optional[Union[complex, int]]
      c = ...  # type: Optional[Union[complex, int, str]]
      d = ...  # type: int
      e = ...  # type: Optional[int]
      f = ...  # type: Optional[Union[complex, int]]
      g = ...  # type: Optional[Union[complex, int, str]]
      h = ...  # type: int
      i = ...  # type: int
      """)

  def testFromKeys(self):
    ty = self.Infer("""
      d1 = dict.fromkeys([1])
      d2 = dict.fromkeys([1], 0)
      d3 = dict.fromkeys("123")
      d4 = dict.fromkeys(bytearray("x"))
      d6 = dict.fromkeys(iter("123"))
      d7 = dict.fromkeys({True: False})
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d1 = ...  # type: Dict[int, None]
      d2 = ...  # type: Dict[int, int]
      d3 = ...  # type: Dict[str, None]
      d4 = ...  # type: Dict[int, None]
      d6 = ...  # type: Dict[str, None]
      d7 = ...  # type: Dict[bool, None]
    """)

  def testRedefinedBuiltin(self):
    ty = self.Infer("""
      class BaseException(Exception): pass
      class CryptoException(BaseException, ValueError): pass
    """, deep=False)
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: int
      x2 = ...  # type: int
      x3 = ...  # type: float or complex
      x4 = ...  # type: int or float or complex
      x5 = ...  # type: List[int or str]
    """)

  def testReversed(self):
    ty, errors = self.InferWithErrors("""\
      x1 = reversed(range(42))
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
      x1 = filter(None, "")
      x2 = filter(None, bytearray(""))
      x3 = filter(None, (True, False))
      x4 = filter(None, {True, False})
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      x1 = ...  # type: str
      x2 = ...  # type: List[int]
      x3 = ...  # type: Tuple[bool, ...]
      x4 = ...  # type: List[bool]
    """)

  def testStrJoin(self):
    ty = self.Infer("""
      a = ",".join([])
      c = ",".join(["foo"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: str
      c = ...  # type: str
    """)

  def testBytearrayJoin(self):
    ty = self.Infer("""
      b = bytearray()
      x1 = b.join([])
      x3 = b.join([b])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bytearray
      x1 = ...  # type: bytearray
      x3 = ...  # type: bytearray
    """)

  def testReduce(self):
    _, errors = self.InferWithErrors("""\
      reduce(lambda x, y: x+y, [1,2,3]).real
      reduce(lambda x, y: x+y, ["foo"]).upper()
      reduce(lambda x, y: 4, "foo").real
      reduce(lambda x, y: 4, [], "foo").upper()
      reduce(lambda x, y: "s", [1,2,3], 0).upper()
    """)
    self.assertErrorLogIs(errors, [
        (3, "attribute-error", "real.*str")
    ])

  def testDictPopItem(self):
    ty = self.Infer("""
      v = {"a": 1}.popitem()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      v = ...  # type: Tuple[str, int]
    """)

  def testLongConstant(self):
    ty = self.Infer("""
      MAX_VALUE = 2**64
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      MAX_VALUE = ...  # type: int
    """)

  def testIter(self):
    ty = self.Infer("""
      x1 = iter("hello")
      x3 = iter(bytearray(42))
      x4 = iter(x for x in [42])
      x5 = iter([42])
      x6 = iter((42,))
      x7 = iter({42})
      x8 = iter({"a": 1})
      x9 = iter(int, 42)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator, Iterator
      x1 = ...  # type: Iterator[str]
      x3 = ...  # type: bytearray_iterator
      x4 = ...  # type: Generator[int, Any, Any]
      x5 = ...  # type: listiterator[int]
      x6 = ...  # type: tupleiterator[int]
      x7 = ...  # type: setiterator[int]
      x8 = ...  # type: `dictionary-keyiterator`[str]
      # The "nothing" is due to pytype ignoring Callable parameters and
      # therefore not seeing the type parameter value tucked away in _RET.
      x9 = ...  # type: `callable-iterator`[int]
    """)

  def testListInit(self):
    ty = self.Infer("""
      l1 = list()
      l2 = list([42])
      l5 = list(iter([42]))
      l6 = list(reversed([42]))
      l7 = list(iter((42,)))
      l8 = list(iter({42}))
      l9 = list((42,))
      l10 = list({42})
      l11 = list("hello")
      l12 = list(iter(bytearray(42)))
      l13 = list(iter(range(42)))
      l14 = list(x for x in [42])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l1 = ...  # type: List[nothing]
      l2 = ...  # type: List[int]
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
      t5 = tuple(iter([42]))
      t6 = tuple(reversed([42]))
      t7 = tuple(iter((42,)))
      t8 = tuple(iter({42}))
      t9 = tuple((42,))
      t10 = tuple({42})
      t11 = tuple("hello")
      t12 = tuple(iter(bytearray(42)))
      t13 = tuple(iter(range(42)))
      t14 = tuple(x for x in [42])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t1 = ...  # type: Tuple[nothing, ...]
      t2 = ...  # type: Tuple[int, ...]
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
    self.Check("""\
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[int or str]
      x2 = ...  # type: List[int or str]
      x3 = ...  # type: List[int or str]
      x4 = ...  # type: List[int or str]
    """)

  def testSorted(self):
    ty = self.Infer("""
      x1 = sorted("hello")
      x3 = sorted(bytearray("hello"))
      x4 = sorted([])
      x5 = sorted([42], reversed=True)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x1 = ...  # type: List[str]
      x3 = ...  # type: List[int]
      x4 = ...  # type: List[nothing]
      x5 = ...  # type: List[int]
    """)

  def testEnumerate(self):
    ty = self.Infer("""
      x1 = enumerate([42])
      x2 = enumerate((42,))
      x3 = enumerate(x for x in range(5))
    """, deep=False)
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      x1 = ...  # type: frozenset[int]
      x2 = ...  # type: frozenset[int]
      x3 = ...  # type: frozenset[str]
    """)

  def testFrozenSetLiteral(self):
    # In python2 this calls LOAD_CONST 'foo'; BUILD_SET, but python3 calls
    # LOAD_CONST frozenset(['foo']) directly. Test that both versions work.
    ty = self.Infer("""
      a = "foo" in {"foo"}
    """)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: bool
    """)

  def testFuncTools(self):
    self.Check("""
      import functools
    """)

  def testABC(self):
    self.Check("""
      import abc
    """)

  def testSetDefault(self):
    ty = self.Infer("""
      x = {}
      x['bar'] = 3
      y = x.setdefault('foo', 3.14)
      z = x['foo']
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Optional
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Dict

      x1 = ...  # type: Dict[str, int]
      y1 = ...  # type: int

      x2 = ...  # type: dict
      y2 = ...  # type: Any
    """)

  def testRedefineNext(self):
    ty = self.Infer("""
      next = 42
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      next = ...  # type: int
    """)

  def testOsEnvironCopy(self):
    self.Check("""
      import os
      os.environ.copy()["foo"] = "bar"
    """)

  def testBytearrayInit(self):
    self.Check("""
      bytearray(42)
      bytearray([42])
      bytearray(u"hello", "utf-8")
      bytearray(u"hello", "utf-8", "")
    """)

  def testCompile(self):
    self.Check("""
      code = compile("1 + 2", "foo.py", "single")
    """)

  def testIntInit(self):
    self.Check("""
      int(42)
      int(42.0)
      int("42")
      int(u"42")
      int()
    """)

  def testExec(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        x = exec
      """)
      self.Check("""\
        import foo
        foo.x("a = 2")
      """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
