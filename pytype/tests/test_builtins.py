"""Tests of builtins (in pytd/builtins/__builtins__.pytd)."""

import unittest
from pytype.tests import test_inference


class BuiltinTests(test_inference.InferenceTest):

  def testRepr1(self):
    with self.Infer("""
      def t_testRepr1(x):
        return repr(x)
      t_testRepr1(4)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testRepr1(x: int) -> str
      """)

  def testRepr2(self):
    with self.Infer("""
      def t_testRepr2(x):
        return repr(x)
      t_testRepr2(4)
      t_testRepr2(1.234)
      t_testRepr2('abc')
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testRepr2(x: float or int or str) -> str
      """)

  def testRepr3(self):
    with self.Infer("""
      def t_testRepr3(x):
        return repr(x)
      t_testRepr3(__any_object__())
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testRepr3(x) -> str
      """)

  def testEvalSolve(self):
    with self.Infer("""
      def t_testEval(x):
        return eval(x)
      t_testEval(4)
    """, deep=False, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        # TODO(pludemann): should this return `?` instead of `object`?
        def t_testEval(x: int) -> ?
      """)

  def testIsinstance1(self):
    with self.Infer("""
      def t_testIsinstance1(x):
        # TODO: if isinstance(x, int): return "abc" else: return None
        return isinstance(x, int)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testIsinstance1(x: object) -> bool
      """)

  @unittest.skip("Broken - needs more sophisticated booleans")
  def testIsinstance2(self):
    with self.Infer("""
      def t_testIsinstance2(x):
        assert isinstance(x, int)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        # TODO(pludemann): currently does (x: object)
        def t_testIsinstance2(x: int) -> NoneType
      """)

  def testPow1(self):
    with self.Infer("""
      def t_testPow1():
        # pow(int, int) returns int, or float if the exponent is negative, or
        # long if the result is larger than an int. Hence, it's a handy function
        # for testing UnionType returns.
        return pow(1, -2)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testPow1() -> float or int or long
      """)

  def testPow2(self):
    with self.Infer("""
      def t_testPow2(x, y):
        # pow(int, int) returns int, or float if the exponent is negative, or
        # long if the result is larger than an int. Hence, it's a handy function
        # for testing UnionType returns.
        return pow(x, y)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testPow2(x: bool or complex or float or int or long, y: bool or complex or float or int or long) -> bool or complex or float or int or long
      """)

  def testMax1(self):
    with self.Infer("""
      def t_testMax1():
        # max is a parameterized function
        return max(1, 2)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testMax1() -> int
        """)

  def testMax2(self):
    # TODO(kramm): This test takes over six seconds
    with self.Infer("""
      def t_testMax2(x, y):
        # max is a parameterized function
        return max(x, y)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testMax2(x: object, y: object) -> ?
        """)

  def testDict(self):
    with self.Infer("""
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
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testDict() -> float or int
        # _i1_, _i2_ capture the more precise definitions of the ~dict, ~list
        def _i1_(x: List[float or int, ...]) -> List[float or int, ...]
        def _i2_(x: dict[complex or str, float or int]) -> Dict[complex or str, float or int]
        # TODO(pludemann): solve_unknowns=True removes this:
        # class `~dict`:
        #   def __setitem__(self, i: complex, y: float) -> NoneType
        #   def __setitem__(self, i: str, y: int) -> NoneType
        #   def values(self) -> List[float or int, ...]
        # class `~list`:
        #   def __getitem__(self, index: int) -> float or int
      """)

  def testDictDefaults(self):
    with self.Infer("""
    def t_testDictDefaults(x):
      d = {}
      res = d.setdefault(x, str(x))
      _i_(d)
      return res
    def _i_(x):
      return x
    t_testDictDefaults(3)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testDictDefaults(x: int) -> str
        # _i_ captures the more precise definition of the dict
        def _i_(x: dict[int, str]) -> dict[int, str]
        # TODO(pludemann): solve_unknowns=True removes this:
        # class `~dict`:
        #  def setdefault(self, k: int) -> str
        # class `~str`:
        #   def __init__(self, object: int) -> NoneType
      """)

  def testDictGet(self):
    with self.Infer("""
      def f():
        mydict = {"42": 42}
        return mydict.get("42")
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int or NoneType
      """)

  def testDictGetOrDefault(self):
    with self.Infer("""
      def f():
        mydict = {"42": 42}
        return mydict.get("42", False)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int or bool
      """)

  def testListInit0(self):
    with self.Infer("""
    def t_testListInit0(x):
      return list(x)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testListInit0(x: object) -> List[?, ...]
      """)

  def testListInit1(self):
    with self.Infer("""
    def t_testListInit1(x, y):
      return x + [y]
    """, deep=True, solve_unknowns=True, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testListInit1(x: List[object, ...], y) -> List[?, ...]
      """)

  def testListInit2(self):
    with self.Infer("""
    def t_testListInit2(x, i):
      return x[i]
    z = __any_object__
    t_testListInit2(__any_object__, z)
    print z + 1
    """, deep=False, solve_unknowns=True, reverse_operators=False) as ty:
      self.assertTypesMatchPytd(ty, """
        z = ...  # type: bool or complex or float or int or long

        def t_testListInit2(x: object, i: bool or complex or float or int or long) -> ?
      """)

  def testListInit3(self):
    with self.Infer("""
    def t_testListInit3(x, i):
      return x[i]
    t_testListInit3([1,2,3,'abc'], 0)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testListInit3(x: List[int or str, ...], i: int) -> int or str
      """)

  def testListInit4(self):
    # TODO(kramm): This test takes over six seconds
    with self.Infer("""
    def t_testListInit4(x):
      return _i_(list(x))[0]
    def _i_(x):
      return x
    t_testListInit4(__any_object__)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      # TODO(kramm): "object" below is only correct as long as return types and
      #              type params are covariant. If they'd be invariant, the
      #              below would be wrong.
      self.assertTypesMatchPytd(ty, """
        def t_testListInit4(x) -> ?
        # _i_ captures the more precise definition of the list
        def _i_(x: List[object, ...]) -> List[?, ...]
      """)

  def testAbsInt(self):
    with self.Infer("""
      def t_testAbsInt(x):
        return abs(x)
      t_testAbsInt(1)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testAbsInt(x: int) -> int
    """)

  def testAbs(self):
    with self.Infer("""
      def t_testAbs(x):
        return abs(x)
      t_testAbs(__any_object__)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testAbs(x: bool or complex or float or int or long) -> bool or float or int or long
      """)

  def testCmp(self):
    with self.Infer("""
      def t_testCmp(x, y):
        return cmp(x, y)
    """, deep=True, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
      def t_testCmp(x, y) -> bool
      """)

  def testCmpMulti(self):
    with self.Infer("""
      def t_testCmpMulti(x, y):
        return cmp(x, y)
      t_testCmpMulti(1, 2)
      t_testCmpMulti(1, 2.0)
      t_testCmpMulti(1.0, 2)
      # TODO(pludemann): add more tests
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testCmpMulti(x: float or int, y: int) -> bool
        def t_testCmpMulti(x: int, y: float) -> bool
      """)

  def testCmpStr(self):
    with self.Infer("""
      def t_testCmpStr(x, y):
        return cmp(x, y)
      t_testCmpStr("abc", "def")
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testCmpStr(x: str, y: str) -> bool
      """)

  def testCmpStr2(self):
    with self.Infer("""
      def t_testCmpStr2(x, y):
        return cmp(x, y)
      t_testCmpStr2("abc", __any_object__)
    """, deep=False, solve_unknowns=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def t_testCmpStr2(x: str, y) -> bool
      """)

  def testTuple(self):
    # smoke test
    self.Infer("""
      def f(x):
        return x
      def g(args):
        f(*tuple(args))
    """, deep=True, solve_unknowns=False, extract_locals=False)

  def testOpen(self):
    with self.Infer("""
      def f(x):
        with open(x, "r") as fi:
          return fi.read()
      """, deep=True, solve_unknowns=True, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x: str or bytes or buffer or unicode) -> str
      """)

  def testSignal(self):
    with self.Infer("""
      import signal
      def f():
        signal.signal(signal.SIGALRM, 0)
    """, deep=True, solve_unknowns=True, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        signal = ...  # type: module

        def f() -> NoneType
      """)

  def testSysArgv(self):
    with self.Infer("""
      import sys
      def args():
        return ' '.join(sys.argv)
      args()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        sys = ...  # type: module
        def args() -> str
      """)

  def testSetattr(self):
    with self.Infer("""
      class Foo(object):
        def __init__(self, x):
          for attr in x.__dict__:
            setattr(self, attr, getattr(x, attr))
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class Foo(object):
          def __init__(self, x) -> NoneType
      """)

  def testMap1(self):
    with self.Infer("""
      def f(input_string, sub):
        return ''.join(map(lambda ch: ch, input_string))
    """, deep=True, solve_unknowns=True) as ty:
      self.assertOnlyHasReturnType(
          ty.Lookup("f"), self.strorunicodeorbytes)

  def testMap2(self):
    with self.Infer("""
      class Foo(object):
        pass

      def f():
        return map(lambda x: x, [Foo()])
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        class Foo(object):
          pass

        def f() -> List[?, ...]
      """)

  def testArraySmoke(self):
    with self.Infer("""
      import array
      class Foo(object):
        def __init__(self):
          array.array('i')
    """, deep=True, solve_unknowns=False) as ty:
      ty.Lookup("Foo")  # smoke test

  def testArray(self):
    with self.Infer("""
      import array
      class Foo(object):
        def __init__(self):
          self.bar = array.array('i')
    """, deep=True, solve_unknowns=False) as ty:
      self.assertTypesMatchPytd(ty, """
        array = ...  # type: module
        class Foo(object):
          bar = ...  # type: array.array
      """)

  def testInheritFromBuiltin(self):
    with self.Infer("""
      class Foo(list):
        pass
    """, deep=True, solve_unknowns=False) as ty:
      self.assertTypesMatchPytd(ty, """
        class Foo(List[?, ...]):
          pass
      """)

  def testOsPath(self):
    with self.Infer("""
      import os
      class Foo(object):
        bar = os.path.join('hello', 'world')
    """, deep=True, solve_unknowns=True) as ty:
      ty.Lookup("Foo")  # smoke test

  def testIsInstance(self):
    with self.Infer("""
      class Bar(object):
        def foo(self):
          return isinstance(self, Baz)

      class Baz(Bar):
        pass
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Bar(object):
        def foo(self) -> bool

      class Baz(Bar):
        pass
      """)

  def testTime(self):
    with self.Infer("""
      import time
      def f(x):
        if x:
          return time.mktime(())
        else:
          return 3j
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        time = ...  # type: module

        def f(x) -> complex or float
      """)

  def testDivMod(self):
    with self.Infer("""
      def seed(self, a=None):
        a = long(0)
        divmod(a, 30268)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def seed(self, ...) -> NoneType
      """)

  def testDivMod2(self):
    with self.Infer("""
      def seed(self, a=None):
        if a is None:
          a = int(16)
        return divmod(a, 30268)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def seed(self, ...) -> Tuple[int or long or float or complex, ...]
      """)

  def testDivMod3(self):
    with self.Infer("""
      def seed(self, a=None):
        if a is None:
          a = long(16)
        return divmod(a, 30268)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def seed(self, ...) -> Tuple[int or long or float or complex, ...]
      """)

  def testOsOpen(self):
    with self.Infer("""
      import os
      def f():
        return open("/dev/null")
      def g():
        return os.open("/dev/null", os.O_RDONLY, 0777)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        os = ...  # type: module

        def f() -> file
        def g() -> int
      """)

  def testJoin(self):
    with self.Infer("""
      def f(elements):
        return ",".join(t for t in elements)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(elements) -> str
      """)

  def testVersionInfo(self):
    with self.Infer("""
      import sys
      def f():
        return 'py%d' % sys.version_info[0]
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        sys = ...  # type: module
        def f() -> str
      """)

  def testInheritFromNamedTuple(self):
    with self.Infer("""
      import collections

      class Foo(
          collections.namedtuple('_Foo', 'x y z')):
        pass
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        collections = ...  # type: module

        class Foo(?):
          pass
      """)

  def testStoreAndLoadFromNamedTuple(self):
    with self.Infer("""
      import collections
      t = collections.namedtuple('', ['x', 'y', 'z'])
      t.x = 3
      t.y = "foo"
      t.z = 1j
      x = t.x
      y = t.y
      z = t.z
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      t = ...  # type: ?  # TODO(kramm): Should this be a class, with attribute x, y and z?
      x = ...  # type: int
      y = ...  # type: str
      z = ...  # type: complex
      """)

  def testTypeEquals(self):
    with self.Infer("""
      def f(n):
        return type(n) == type(0)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(n) -> bool
      """)

  def testTypeEquals2(self):
    with self.Infer("""
      import types
      def f(num):
        return type(num) == types.IntType
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        types = ...  # type: module
        def f(num) -> bool
      """)

  def testDateTime(self):
    with self.Infer("""
      import datetime

      def f(date):
        return date.ctime()
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        datetime = ...  # type: module
        def f(date: datetime.datetime or datetime.date) -> bytes or str
    """)

  def testFromUTC(self):
    with self.Infer("""
      import datetime

      def f(tz):
        tz.fromutc(None)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        datetime = ...  # type: module
        def f(tz: datetime.tzinfo) -> NoneType
    """)

  def testDivModWithUnknown(self):
    with self.Infer("""
      def f(x, y):
        divmod(x, __any_object__)
        return divmod(3, y)
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x: bool or int or float or complex or long,
              y: bool or int or float or complex or long) -> Tuple[int or float or complex or long, ...]
      """)

  def testDefaultDict(self):
    with self.Infer("""
      import collections
      r = collections.defaultdict()
      r[3] = 3
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        collections = ...  # type: module
        r = ...  # type: collections.defaultdict
      """)

if __name__ == "__main__":
  test_inference.main()
