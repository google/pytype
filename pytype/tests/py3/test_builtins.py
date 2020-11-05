"""Tests of builtins (in pytd/builtins/{version}/__builtins__.pytd)."""

from pytype import file_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class BuiltinTests(test_base.TargetPython3BasicTest):
  """Tests for builtin methods and classes."""

  def test_bool_return_value(self):
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

  def test_sum_return(self):
    self.Check("""
      from typing import List
      def f(x: List[float]) -> float:
        return sum(x)
    """)

  def test_print_function(self):
    self.Check("""
      from __future__ import print_function
      import sys
      print(file=sys.stderr)
    """)

  def test_filename(self):
    self.Check("""
      def foo(s: str) -> str:
        return s
      foo(__file__)
      """, filename="foobar.py")

  def test_super(self):
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

  def test_bytearray_slice(self):
    self.Check("""
      def f(x: bytearray) -> bytearray:
        return x[1:]
      def g(x: bytearray) -> bytearray:
        return x[1:5:2]
    """)

  def test_set_length(self):
    self.Check("""
      from typing import Set
      x = ...  # type: Set[int]
      len(x)
      len(set())
    """)

  def test_sequence_length(self):
    self.Check("""
      from typing import Sequence
      x = ...  # type: Sequence
      len(x)
    """)

  def test_mapping_length(self):
    self.Check("""
      from typing import Mapping
      x = ...  # type: Mapping
      len(x)
    """)


class BuiltinPython3FeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for builtin methods and classes."""

  def test_builtins(self):
    self.Check("""
      import builtins
    """)

  def test_unicode(self):
    self.CheckWithErrors("""
      unicode("foo")  # name-error
    """)

  def test_bytes_iteration(self):
    self.CheckWithErrors("""
      def f():
        for x in bytes():
          return bytes() + x  # unsupported-operands
    """)

  def test_inplace_division(self):
    self.Check("""
      x, y = 24, 3
      x /= y
      assert x == 8.0 and y == 3
      assert isinstance(x, float)
      x /= y
      assert x == (8.0/3.0) and y == 3
      assert isinstance(x, float)
    """)

  def test_removed_dict_methods(self):
    self.CheckWithErrors("""
      {}.iteritems  # attribute-error
      {}.iterkeys  # attribute-error
      {}.itervalues  # attribute-error
      {}.viewitems  # attribute-error
      {}.viewkeys  # attribute-error
      {}.viewvalues  # attribute-error
    """)

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
      b = ...  # type: str
      d = ...  # type: str
      e = ...  # type: str
      f = ...  # type: str
      g = ...  # type: str
      h = ...  # type: str
    """)

  def test_str_is_hashable(self):
    self.Check("""
      from typing import Any, Dict, Hashable
      def f(x: Dict[Hashable, Any]):
        return x["foo"]
      f({'foo': 1})
    """)

  def test_bytearray_join(self):
    ty = self.Infer("""
      b = bytearray()
      x2 = b.join([b"x"])
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
      x = ...  # type: Iterator[str]
    """)

  def test_iter1(self):
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

  def test_from_keys(self):
    ty = self.Infer("""
      d = dict.fromkeys(u"x")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      d = ...  # type: Dict[str, None]
    """)

  def test_dict_keys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.keys() & {1, 2, 3}
      b = m.keys() - {1, 2, 3}
      c = m.keys() | {1, 2, 3}
      d = m.keys() ^ {1, 2, 3}
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set, Union
      m = ...  # type: Dict[str, None]
      a = ...  # type: Set[str]
      b = ...  # type: Set[str]
      c = ...  # type: Set[Union[int, str]]
      d = ...  # type: Set[Union[int, str]]
    """)

  def test_open(self):
    ty = self.Infer("""
      f1 = open("foo.py", "r")
      f2 = open("foo.pickled", "rb")
      v1 = f1.read()
      v2 = f2.read()
      def open_file1(mode):
        f = open("foo.x", mode)
        return f, f.read()
      def open_file2(mode: str):
        f = open("foo.x", mode)
        return f, f.read()
    """)
    # The different return types of open_file1 and open_file2 are due to a quirk
    # of our implementation of Literal: Any matches a Literal, but a
    # non-constant instance of the Literal's type does not, so in the first
    # case, multiple signatures match and pytype falls back to Any, whereas in
    # the second, only the fallback signature matches.
    self.assertTypesMatchPytd(ty, """
      from typing import Any, BinaryIO, IO, TextIO, Tuple, Union
      f1: TextIO
      f2: BinaryIO
      v1: str
      v2: bytes
      def open_file1(mode) -> Tuple[Any, Any]: ...
      def open_file2(mode: str) -> Tuple[IO[Union[bytes, str]], Union[bytes, str]]: ...
    """)

  def test_open_extended_file_modes(self):
    ty = self.Infer("""
      f1 = open("f1", "rb+")
      f2 = open("f2", "w+t")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import BinaryIO, TextIO
      f1: BinaryIO
      f2: TextIO
    """)

  def test_filter(self):
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
      def f(x: int) -> None: ...
      x1 = ...  # type: Iterator[str]
      x2 = ...  # type: Iterator[int]
      x3 = ...  # type: Iterator[bool, ...]
      x4 = ...  # type: Iterator[bool]
      x5 = ...  # type: Iterator[int]
      x6 = ...  # type: Iterator[int]
      x7 = ...  # type: Iterator[str]
      """)

  def test_filter_types(self):
    self.Check("""
      from typing import Iterator, List, Optional, Tuple, Union
      def f(xs: List[Optional[int]]) -> Iterator[int]:
        return filter(None, xs)
      def g(x: Tuple[int, str, None]) -> Iterator[Union[int, str]]:
        return filter(None, x)
    """)

  def test_sorted(self):
    ty = self.Infer("""
      x = sorted(u"hello")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      x = ...  # type: List[str]
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
      from typing import Iterator, Tuple, Union
      a = ...  # type: Iterator[Tuple[str, str]]
      b = ...  # type: Iterator[nothing]
      c = ...  # type: Iterator[Tuple[Union[int, complex]]]
      d = ...  # type: Iterator[nothing]
      e = ...  # type: Iterator[nothing]
      f = ...  # type: Iterator[Tuple[complex, int]]
      """)

  def test_map_basic(self):
    ty = self.Infer("""
      v = map(int, ("0",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      v = ...  # type: Iterator[int]
    """)

  def test_map(self):
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

      def f() -> Iterator: ...
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
      from typing import Any, List, Iterator
      lst1 = ...  # type: List[nothing]
      lst2 = ...  # type: List[nothing]
      lst3 = ...  # type: Iterator[nothing]
    """)

  def test_dict(self):
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
      def t_testDict() -> Union[float, int]: ...
      # _i1_, _i2_ capture the more precise definitions of the ~dict, ~list
      def _i1_(x: List[float]) -> List[Union[float, int]]: ...
      def _i2_(x: dict[Union[complex, str], Union[float, int]]) -> Dict[Union[complex, str], Union[float, int]]: ...
    """)

  def test_list_init(self):
    ty = self.Infer("""
      l3 = list({"a": 1}.keys())
      l4 = list({"a": 1}.values())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l3 = ...  # type: List[str]
      l4 = ...  # type: List[int]
    """)

  def test_tuple_init(self):
    ty = self.Infer("""
      t3 = tuple({"a": 1}.keys())
      t4 = tuple({"a": 1}.values())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t3 = ...  # type: Tuple[str, ...]
      t4 = ...  # type: Tuple[int, ...]
    """)

  def test_items(self):
    ty = self.Infer("""
      lst = list({"a": 1}.items())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      lst = ...  # type: List[Tuple[str, int]]
    """)

  def test_int_init(self):
    _, errors = self.InferWithErrors("""
      int(0, 1)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Union\[bytes, str\].*int"})

  def test_removed_builtins(self):
    self.CheckWithErrors("""
      long  # name-error
      {}.has_key  # attribute-error
    """)

  def test_range(self):
    ty, _ = self.InferWithErrors("""
      xrange(3)  # name-error
      v = range(3)
      v[0]
      v[:]
      x, y, z = v.start, v.stop, v.step
    """)
    self.assertTypesMatchPytd(ty, """
      v: range
      x: int
      y: int
      z: int
    """)

  def test_create_str(self):
    self.Check("""
      str(b"foo", "utf-8")
    """)

  def test_bytes_constant(self):
    ty = self.Infer("v = b'foo'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: bytes")

  def test_unicode_constant(self):
    ty = self.Infer("v = 'foo\\u00e4'")
    self.assertTypesMatchPytd(ty, "v = ...  # type: str")

  def test_memoryview(self):
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

  def test_memoryview_methods(self):
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

  def test_memoryview_contextmanager(self):
    ty = self.Infer("""
      with memoryview(b'abc') as v:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      v = ...  # type: memoryview
    """)

  def test_array_tobytes(self):
    ty = self.Infer("""
      import array
      def t_testTobytes():
        return array.array('B').tobytes()
    """)
    self.assertTypesMatchPytd(ty, """
      array = ...  # type: module
      def t_testTobytes() -> bytes: ...
    """)

  def test_iterator_builtins(self):
    ty = self.Infer("""
      v1 = map(int, ["0"])
      v2 = zip([0], [1])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator, Tuple
      v1 = ...  # type: Iterator[int]
      v2 = ...  # type: Iterator[Tuple[int, int]]
    """)

  def test_next(self):
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

  def test_aliased_error(self):
    # In Python 3, EnvironmentError and IOError became aliases for OSError.
    self.Check("""
      def f(e: OSError): ...
      def g(e: IOError): ...
      f(EnvironmentError())
      g(EnvironmentError())
    """)

  def test_os_error_subclasses(self):
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

  def test_raw_input(self):
    # Removed in Python 3:
    self.CheckWithErrors("raw_input  # name-error")

  def test_clear(self):
    # new in Python 3
    self.Check("""
      bytearray().clear()
      [].clear()
    """)

  def test_copy(self):
    # new in python 3
    self.Check("""
      bytearray().copy()
      [].copy()
    """)

  def test_round(self):
    ty = self.Infer("""
      v1 = round(4.2)
      v2 = round(4.2, 1)
    """)
    self.assertTypesMatchPytd(ty, """
      v1: int
      v2: float
    """)

  def test_int_bytes_conversion(self):
    ty = self.Infer("""
      bytes_obj = (42).to_bytes(1, "little")
      int_obj = int.from_bytes(b"*", "little")
    """)
    self.assertTypesMatchPytd(ty, """
      bytes_obj: bytes
      int_obj: int
    """)

  def test_unicode_error(self):
    self.Check("""
      UnicodeDecodeError("", b"", 0, 0, "")
      UnicodeEncodeError("", u"", 0, 0, "")
    """)

  def test_min_max(self):
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

  def test_str_is_not_int(self):
    self.CheckWithErrors("""
      from typing import SupportsInt
      def f(x: SupportsInt): pass
      f("")  # wrong-arg-types
    """)

  def test_str_is_not_float(self):
    self.CheckWithErrors("""
      from typing import SupportsFloat
      def f(x: SupportsFloat): pass
      f("")  # wrong-arg-types
    """)

  @test_utils.skipBeforePy((3, 8), "__index__ support is new in 3.8")
  def test_int_from_index(self):
    self.Check("""
      class Foo:
        def __index__(self):
          return 0
      int(Foo())
    """)

  def test_bytearray_compatible_with_bytes(self):
    self.Check("""
      def f(x):
        # type: (bytes) -> None
        pass
      f(bytearray())
    """)


test_base.main(globals(), __name__ == "__main__")
