"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd)."""

from pytype import file_utils
from pytype.tests import test_base


class BuiltinTests(test_base.TargetPython27FeatureTest):
  """Tests for builtin methods and classes."""

  def test_long(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: long): ...
      """)
      self.Check("""
        import foo
        foo.f(42)
      """, pythonpath=[d.path])

  def test_str_join(self):
    ty = self.Infer("""
      b = u",".join([])
      d = u",".join(["foo"])
      e = ",".join([u"foo"])
      f = u",".join([u"foo"])
      g = ",".join([u"foo", "bar"])
      h = u",".join([u"foo", "bar"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      b = ...  # type: unicode
      d = ...  # type: unicode
      e = ...  # type: unicode
      f = ...  # type: unicode
      g = ...  # type: Union[str, unicode]
      h = ...  # type: unicode
    """)

  def test_bytearray_join(self):
    ty = self.Infer("""
      b = bytearray()
      x2 = b.join(["x"])
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bytearray
      x2 = ...  # type: bytearray
    """)

  def test_iter(self):
    ty = self.Infer("""
      x = iter(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      x = ...  # type: Iterator[unicode]
    """)

  def test_from_keys(self):
    ty = self.Infer("""
      d = dict.fromkeys(u"x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[unicode, None]
    """)

  def test_dict_iterators(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Iterator
        def need_iterator(x: Iterator[Any]) -> None: ...
      """)
      ty = self.Infer("""
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

  def test_dict_keys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.viewkeys() & {1, 2, 3}
      b = m.viewkeys() - {1, 2, 3}
      c = m.viewkeys() | {1, 2, 3}
      d = m.viewkeys() ^ {1, 2, 3}
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set, Union
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[Union[int, str]]
      d = ...  # type: Set[Union[int, str]]
    """)

  def test_filter(self):
    ty = self.Infer("""
      import re
      x1 = filter(None, "")
      x2 = filter(None, bytearray(""))
      x3 = filter(None, (True, False))
      x4 = filter(None, {True, False})
      x5 = filter(None, {1: None}.iterkeys())
      x6 = filter(None, u"")
      x7 = filter(re.compile("").search, ("",))
      x8 = filter(re.compile("").search, [""])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      re: module
      x1: str
      x2: List[int]
      x3: Tuple[bool, ...]
      x4: List[bool]
      x5: List[int]
      x6: unicode
      x7: Tuple[str, ...]
      x8: List[str]
    """)

  def test_sorted(self):
    ty = self.Infer("""
      x = sorted(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x = ...  # type: List[unicode]
    """)

  def test_zip(self):
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

  def test_os_open(self):
    ty = self.Infer("""
      import os
      def f():
        return open("/dev/null")
      def g():
        return os.open("/dev/null", os.O_RDONLY, 0777)
    """)
    self.assertTypesMatchPytd(ty, """
      os = ...  # type: module

      def f() -> file: ...
      def g() -> int: ...
    """)

  def test_map_basic(self):
    ty = self.Infer("""
      v = map(int, ("0",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      v = ...  # type: List[int]
    """)

  def test_map(self):
    ty = self.Infer("""
      class Foo(object):
        pass

      def f():
        return map(lambda x: x, [Foo()])
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        pass

      def f() -> list: ...
    """)

  def test_map1(self):
    ty = self.Infer("""
      def f(input_string, sub):
        return ''.join(map(lambda ch: ch, input_string))
    """)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.str)

  def test_map2(self):
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

  def test_map_none_function(self):
    ty = self.Infer("l = map(None, [1,2,3])")
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l = ...  # type: List[int]
      """)

  def test_map_none_function_two_iterables(self):
    ty = self.Infer("""
      l1 = [1,2,3]
      l2 = [4,5,6]
      l3 = map(None, l1, l2)
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      l1 = ...  # type: List[int]
      l2 = ...  # type: List[int]
      l3 = ...  # type: List[Tuple[int, int]]
      """)

  def test_map_none_func_different_types(self):
    ty = self.Infer("""
      l1 = [1,2,3]
      l2 = ['a', 'b', 'c']
      l3 = map(None, l1, l2)
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      l1 = ...  # type: List[int]
      l2 = ...  # type: List[str]
      l3 = ...  # type: List[Tuple[int, str]]
      """)

  def test_map_none_func_many_iters(self):
    # Currently, 2/__builtins__.pytd special cases map(function=None, ...) with
    # 2 iterable arguments. See that it handles the general case too.
    ty = self.Infer("""
      l = map(None, [1,2], ['a', 'b'], [(3, 'c'), (4, 'b')])
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      l = ...  # type: List[Tuple]
      """)

  def test_unpack_map_none_func_many_iters(self):
    ty = self.Infer("""
      for a, b, c in map(None, [1, 2], ['a', 'b'], [(3, 'c'), (4, 'b')]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      a = ...  # type: Any
      b = ...  # type: Any
      c = ...  # type: Any
    """)

  def test_dict(self):
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
      from typing import Dict, List, Union
      def t_testDict() -> Union[float, int]: ...
      # _i1_, _i2_ capture the more precise definitions of the ~dict, ~list
      def _i1_(x: List[float]) -> List[float]: ...
      def _i1_(x: List[int]) -> List[int]: ...
      def _i2_(x: dict[Union[complex, str], Union[float, int]]) -> Dict[Union[complex, str], Union[float, int]]: ...
    """)

  def test_list_init(self):
    ty = self.Infer("""
      l3 = list({"a": 1}.iterkeys())
      l4 = list({"a": 1}.itervalues())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l3 = ...  # type: List[str]
      l4 = ...  # type: List[int]
    """)

  def test_tuple_init(self):
    ty = self.Infer("""
      t3 = tuple({"a": 1}.iterkeys())
      t4 = tuple({"a": 1}.itervalues())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t3 = ...  # type: Tuple[str, ...]
      t4 = ...  # type: Tuple[int, ...]
    """)

  def test_sequence_length(self):
    self.Check("""
      len(buffer(""))
    """)

  def test_exception_message(self):
    ty = self.Infer("""
      class MyException(Exception):
        def get_message(self):
          return self.message
    """)
    self.assertTypesMatchPytd(ty, """
      class MyException(Exception):
        def get_message(self) -> str: ...
    """)

  def test_iter_items(self):
    ty = self.Infer("""
      lst = list({"a": 1}.iteritems())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      lst = ...  # type: List[Tuple[str, int]]
    """)

  def test_int_init(self):
    _, errors = self.InferWithErrors("""
      int(0, 1)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Union\[str, unicode\].*int"})

  def test_add_str_and_bytearray(self):
    ty = self.Infer("""
      v = "abc" + bytearray()
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: bytearray
    """)

  def test_bytearray_setitem(self):
    self.Check("""
      ba = bytearray("hello")
      ba[0] = "j"
      ba[4:] = buffer("yfish")
    """)

  def test_next(self):
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

  def test_str_unicode_mod(self):
    ty = self.Infer("""
        def t_testStrUnicodeMod():
          a = u"Hello"
          return "%s Uni" %(u"Hello")
        t_testStrUnicodeMod()
      """, deep=False)
    self.assertTypesMatchPytd(ty, """
        def t_testStrUnicodeMod() -> unicode: ...
      """)

  def test_round(self):
    ty = self.Infer("""
      v1 = round(4.2)
      v2 = round(4.2, 1)
    """)
    self.assertTypesMatchPytd(ty, """
      v1: float
      v2: float
    """)

  def test_unicode_write(self):
    self.Check("""
      import sys
      sys.stdout.write(u'testing')
    """)


test_base.main(globals(), __name__ == "__main__")
