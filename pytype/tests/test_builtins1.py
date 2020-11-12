"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd).

File 1/3. Split into parts to enable better test parallelism.
"""

import textwrap

from pytype.overlays import collections_overlay
from pytype.pytd import escape
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class BuiltinTests(test_base.TargetIndependentTest):
  """Tests for builtin methods and classes."""

  def test_repr1(self):
    ty = self.Infer("""
      def t_testRepr1(x):
        return repr(x)
      t_testRepr1(4)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testRepr1(x: int) -> str: ...
    """)

  def test_repr2(self):
    ty = self.Infer("""
      def t_testRepr2(x):
        return repr(x)
      t_testRepr2(4)
      t_testRepr2(1.234)
      t_testRepr2('abc')
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testRepr2(x: Union[float, int, str]) -> str: ...
    """)

  def test_repr3(self):
    ty = self.Infer("""
      def t_testRepr3(x):
        return repr(x)
      t_testRepr3(__any_object__())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testRepr3(x) -> str: ...
    """)

  def test_eval_solve(self):
    ty = self.Infer("""
      def t_testEval(x):
        return eval(x)
      t_testEval(4)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testEval(x: int) -> Any: ...
    """)

  def test_isinstance1(self):
    ty = self.Infer("""
      def t_testIsinstance1(x):
        return isinstance(x, int)
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testIsinstance1(x) -> bool: ...
    """)

  def test_isinstance2(self):
    ty = self.Infer("""
      class Bar(object):
        def foo(self):
          return isinstance(self, Baz)

      class Baz(Bar):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
    class Bar(object):
      def foo(self) -> bool: ...

    class Baz(Bar):
      pass
    """)

  def test_pow1(self):
    ty = self.Infer("""
      def t_testPow1():
        # pow(int, int) returns int, or float if the exponent is negative.
        # Hence, it's a handy function for testing UnionType returns.
        return pow(1, -2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testPow1() -> Union[float, int]: ...
    """)

  def test_max1(self):
    ty = self.Infer("""
      def t_testMax1():
        # max is a parameterized function
        return max(1, 2)
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testMax1() -> int: ...
      """)

  def test_max2(self):
    ty = self.Infer("""
      def t_testMax2(x, y):
        # max is a parameterized function
        return max(x, y)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testMax2(x, y) -> Any: ...
      """)

  def test_zip_error(self):
    errors = self.CheckWithErrors("zip([], [], [], 42)  # wrong-arg-types[e]")
    self.assertErrorRegexes(errors, {"e": r"Iterable.*int"})

  def test_dict_defaults(self):
    ty = self.Infer("""
    def t_testDictDefaults(x):
      d = {}
      res = d.setdefault(x, str(x))
      _i_(d)
      return res
    def _i_(x):
      return x
    t_testDictDefaults(3)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testDictDefaults(x: int) -> str: ...
      # _i_ captures the more precise definition of the dict
      def _i_(x: dict[int, str]) -> dict[int, str]: ...
    """)

  def test_dict_get(self):
    ty = self.Infer("""
      def f():
        mydict = {"42": 42}
        return mydict.get("42")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f() -> Union[int, NoneType]: ...
    """)

  def test_dict_get_or_default(self):
    ty = self.Infer("""
      def f():
        mydict = {"42": 42}
        return mydict.get("42", False)
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_list_init0(self):
    ty = self.Infer("""
    def t_testListInit0(x):
      return list(x)
    """)
    self.assertTypesMatchPytd(ty, """
      def t_testListInit0(x) -> list: ...
    """)

  def test_list_init1(self):
    ty = self.Infer("""
    def t_testListInit1(x, y):
      return x + [y]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testListInit1(x, y) -> Any: ...
    """)

  def test_list_init2(self):
    ty = self.Infer("""
    def t_testListInit2(x, i):
      return x[i]
    z = __any_object__
    t_testListInit2(__any_object__, z)
    z + 1
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      z = ...  # type: Any

      def t_testListInit2(x, i) -> Any: ...
    """)

  def test_list_init3(self):
    ty = self.Infer("""
    def t_testListInit3(x, i):
      return x[i]
    t_testListInit3([1,2,3,'abc'], 0)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      def t_testListInit3(x: List[Union[int, str], ...], i: int) -> int: ...
    """)

  def test_list_init4(self):
    ty = self.Infer("""
    def t_testListInit4(x):
      return _i_(list(x))[0]
    def _i_(x):
      return x
    t_testListInit4(__any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def t_testListInit4(x) -> Any: ...
      def _i_(x: list) -> list: ...
    """)

  def test_abs_int(self):
    ty = self.Infer("""
      def t_testAbsInt(x):
        return abs(x)
      t_testAbsInt(1)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testAbsInt(x: int) -> int: ...
  """)

  def test_abs(self):
    ty = self.Infer("""
      def t_testAbs(x):
        return abs(x)
      t_testAbs(__any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      # Since SupportsAbs.__abs__ returns a type parameter, the return type
      # of abs(...) can be anything.
      def t_testAbs(x) -> Any: ...
    """)

  def test_abs_union(self):
    ty = self.Infer("""
      class Foo:
        def __abs__(self):
          return "hello"
      class Bar:
        def __abs__(self):
          return 42
      x = Foo() if __random__ else Bar()
      y = abs(x)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      x = ...  # type: Union[Bar, Foo]
      y = ...  # type: Union[str, int]
      class Bar:
          def __abs__(self) -> int: ...
      class Foo:
          def __abs__(self) -> str: ...
    """)

  def test_cmp(self):
    ty = self.Infer("""
      def t_testCmp(x, y):
        return cmp(x, y)
    """)
    self.assertTypesMatchPytd(ty, """
    def t_testCmp(x, y) -> int: ...
    """)

  def test_cmp_multi(self):
    ty = self.Infer("""
      def t_testCmpMulti(x, y):
        return cmp(x, y)
      t_testCmpMulti(1, 2)
      t_testCmpMulti(1, 2.0)
      t_testCmpMulti(1.0, 2)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def t_testCmpMulti(x: Union[float, int], y: int) -> int: ...
      def t_testCmpMulti(x: int, y: float) -> int: ...
    """)

  def test_cmp_str(self):
    ty = self.Infer("""
      def t_testCmpStr(x, y):
        return cmp(x, y)
      t_testCmpStr("abc", "def")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testCmpStr(x: str, y: str) -> int: ...
    """)

  def test_cmp_str2(self):
    ty = self.Infer("""
      def t_testCmpStr2(x, y):
        return cmp(x, y)
      t_testCmpStr2("abc", __any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def t_testCmpStr2(x: str, y) -> int: ...
    """)

  def test_tuple(self):
    self.Infer("""
      def f(x):
        return x
      def g(args):
        f(*tuple(args))
    """, show_library_calls=True)

  def test_open(self):
    ty = self.Infer("""
      def f(x):
        with open(x, "r") as fi:
          return fi.read()
      """)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> str: ...
    """)

  def test_open_error(self):
    src = "open(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)  # wrong-arg-count"
    self.CheckWithErrors(src)

  def test_signal(self):
    ty = self.Infer("""
      import signal
      def f():
        signal.signal(signal.SIGALRM, 0)
    """)
    self.assertTypesMatchPytd(ty, """
      signal = ...  # type: module

      def f() -> NoneType: ...
    """)

  def test_sys_argv(self):
    ty = self.Infer("""
      import sys
      def args():
        return ' '.join(sys.argv)
      args()
    """, deep=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def args() -> str: ...
    """)

  def test_setattr(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, x):
          for attr in x.__dict__:
            setattr(self, attr, getattr(x, attr))
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __init__(self, x) -> NoneType: ...
    """)

  def test_array_smoke(self):
    ty = self.Infer("""
      import array
      class Foo(object):
        def __init__(self):
          array.array('i')
    """)
    ty.Lookup("Foo")  # smoke test

  def test_array(self):
    ty = self.Infer("""
      import array
      class Foo(object):
        def __init__(self):
          self.bar = array.array('i', [1, 2, 3])
    """)
    self.assertTypesMatchPytd(ty, """
      array = ...  # type: module
      class Foo(object):
        bar = ...  # type: array.array[int]
        def __init__(self) -> None: ...
    """)

  def test_inherit_from_builtin(self):
    ty = self.Infer("""
      class Foo(list):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(list):
        pass
    """)

  def test_os_path(self):
    ty = self.Infer("""
      import os
      class Foo(object):
        bar = os.path.join('hello', 'world')
    """)
    ty.Lookup("Foo")  # smoke test

  def test_hasattr(self):
    ty = self.Infer("""
      class Bar(object):
        pass
      a = hasattr(Bar, 'foo')
    """)
    self.assertTypesMatchPytd(ty, """
    class Bar(object):
      pass
    a : bool
    """)

  def test_time(self):
    ty = self.Infer("""
      import time
      def f(x):
        if x:
          return time.mktime(time.struct_time((1, 2, 3, 4, 5, 6, 7, 8, 9)))
        else:
          return 3j
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      time = ...  # type: module
      def f(x) -> Union[complex, float]: ...
    """)

  def test_div_mod(self):
    ty = self.Infer("""
      def seed(self, a=None):
        a = int(0)
        divmod(a, 30268)
    """)
    self.assertTypesMatchPytd(ty, """
      def seed(self, a=...) -> NoneType: ...
    """)

  def test_div_mod2(self):
    ty = self.Infer("""
      def seed(self, a=None):
        if a is None:
          a = int(16)
        return divmod(a, 30268)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Tuple
      def seed(self, a = ...) -> Tuple[Any, Any]: ...
    """)

  def test_join(self):
    ty = self.Infer("""
      def f(elements):
        return ",".join(t for t in elements)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(elements) -> str: ...
    """)

  def test_version_info(self):
    ty = self.Infer("""
      import sys
      def f():
        return 'py%d' % sys.version_info[0]
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      def f() -> str: ...
    """)

  def test_inherit_from_namedtuple(self):
    ty = self.Infer("""
      import collections

      class Foo(
          collections.namedtuple('_Foo', 'x y z')):
        pass
    """)
    name = escape.pack_namedtuple("_Foo", ["x", "y", "z"])
    ast = collections_overlay.namedtuple_ast(name, ["x", "y", "z"],
                                             self.python_version)
    expected = pytd_utils.Print(ast) + textwrap.dedent("""
      collections = ...  # type: module
      class Foo({name}): ...""").format(name=name)
    self.assertTypesMatchPytd(ty, expected)

  def test_store_and_load_from_namedtuple(self):
    ty = self.Infer("""
      import collections
      t = collections.namedtuple('t', ['x', 'y', 'z'])
      t.x = 3
      t.y = "foo"
      t.z = 1j
      x = t.x
      y = t.y
      z = t.z
    """)
    name = escape.pack_namedtuple("t", ["x", "y", "z"])
    ast = collections_overlay.namedtuple_ast(name, ["x", "y", "z"],
                                             self.python_version)
    expected = pytd_utils.Print(ast) + textwrap.dedent("""
      collections = ...  # type: module
      t = {name}
      x = ...  # type: int
      y = ...  # type: str
      z = ...  # type: complex""").format(name=name)
    self.assertTypesMatchPytd(ty, expected)

  def test_type_equals(self):
    ty = self.Infer("""
      def f(n):
        return type(n) == type(0)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(n) -> Any: ...
    """)

  def test_type_equals2(self):
    ty = self.Infer("""
      import types
      def f(mod):
        return type(mod) == types.ModuleType
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      types = ...  # type: module
      def f(mod) -> Any: ...
    """)

  def test_date_time(self):
    ty = self.Infer("""
      import datetime

      def f(date):
        return date.ctime()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      datetime = ...  # type: module
      def f(date) -> Any: ...
  """)

  def test_from_utc(self):
    ty = self.Infer("""
      import datetime

      def f(tz):
        tz.fromutc(datetime.datetime(1929, 10, 29))
    """)
    self.assertTypesMatchPytd(ty, """
      datetime = ...  # type: module
      def f(tz) -> NoneType: ...
  """)


test_base.main(globals(), __name__ == "__main__")
