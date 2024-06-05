"""Tests of builtins (in stubs/builtins/{version}/__builtins__.pytd)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class MapTest(test_base.BaseTest):
  """Tests for builtin.map."""

  def test_basic(self):
    ty = self.Infer("""
      v = map(int, ("0",))
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      v : Iterator[int]
    """)

  def test_lambda(self):
    ty = self.Infer("""
      class Foo:
        pass

      def f():
        return map(lambda x: x, [Foo()])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator
      class Foo:
        pass

      def f() -> Iterator: ...
    """)

  def test_join(self):
    ty = self.Infer("""
      def f(input_string, sub):
        return ''.join(map(lambda ch: ch, input_string))
    """)
    self.assertTypesMatchPytd(ty, "def f(input_string, sub) -> str: ...")

  def test_empty(self):
    ty = self.Infer("""
      lst1 = []
      lst2 = [x for x in lst1]
      lst3 = map(str, lst2)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List, Iterator
      lst1 : List[nothing]
      lst2 : List[nothing]
      lst3 : Iterator[nothing]
    """)

  def test_heterogeneous(self):
    self.Check("""
      from typing import Union
      def func(a: Union[int, str, float, bool]) -> str:
        return str(a)
      map(func, [1, 'pi', 3.14, True])
    """)

    self.Check("""
      from typing import Iterable, Union
      def func(
          first: Iterable[str], second: str, third: Union[int, bool, float]
      ) -> str:
        return ' '.join(first) + second + str(third)
      map(func,
          [('one', 'two'), {'three', 'four'}, ['five', 'six']],
          'abc',
          [1, False, 3.14])
    """)

  def test_error_message(self):
    errors = self.CheckWithErrors("""
      def func(a: int) -> float:
        return float(a)
      map(func, ['str'])  # wrong-arg-types[e]
    """)
    self.assertErrorSequences(
        errors, {"e": ["Expected", "Iterable[int]", "Actual", "List[str]"]})

  def test_abspath(self):
    self.Check("""
      import os.path
      map(os.path.abspath, [''])
    """)

  def test_protocol(self):
    self.Check("""
      class Foo:
        def __len__(self) -> int:
          return 0
      map(len, [Foo()])
    """)


class BuiltinTests(test_base.BaseTest):
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

  def test_sum_custom(self):
    self.Check("""
      class Foo:
        def __init__(self, v):
          self.v = v
        def __add__(self, other: 'Foo') -> 'Foo':
          return Foo(self.v + other.v)
      assert_type(sum([Foo(0), Foo(1)]), Foo)
    """)

  def test_sum_bad(self):
    self.CheckWithErrors("""
      class Foo:
        pass
      sum([Foo(), Foo()])  # wrong-arg-types
    """)

  def test_print_function(self):
    self.Check("""
      import sys
      print(file=sys.stderr)
    """)

  def test_filename(self):
    self.Check("""
      def foo(s: str) -> str:
        return s
      foo(__file__)
    """)

  def test_super(self):
    with test_utils.Tempdir() as d:
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
        import foo
        from typing import Any, Type
        def f(x) -> None: ...
        def g(x: object) -> None: ...
        def h(x: Any) -> None: ...
        def i(x: type) -> None: ...
        def j(x: Type[super]) -> None: ...
        v : Type[super]
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
      x : Set[int]
      len(x)
      len(set())
    """)

  def test_sequence_length(self):
    self.Check("""
      from typing import Sequence
      x : Sequence
      len(x)
    """)

  def test_mapping_length(self):
    self.Check("""
      from typing import Mapping
      x : Mapping
      len(x)
    """)

  def test_dict_copy(self):
    ty = self.Infer("""
      import collections
      from typing import Dict
      def f1(x: Dict[int, str]):
        return x.copy()
      def f2(x: 'collections.OrderedDict[int, str]'):
        return x.copy()
    """)
    self.assertTypesMatchPytd(ty, """
      import collections
      from typing import Dict, OrderedDict
      def f1(x: Dict[int, str]) -> Dict[int, str]: ...
      def f2(
          x: OrderedDict[int, str]
      ) -> OrderedDict[int, str]: ...
    """)

  def test_format_self(self):
    self.Check("""
      "{self}".format(self="X")
    """)


class BuiltinPython3FeatureTest(test_base.BaseTest):
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
    """)
    self.assertTypesMatchPytd(ty, """
      b : str
      d : str
      e : str
      f : str
      g : str
      h : str
    """)

  @test_utils.skipBeforePy((3, 9), "removeprefix and removesuffix new in 3.9")
  def test_str_remove_prefix_suffix(self):
    ty = self.Infer("""
      a = "prefix_suffix"
      b = a.removeprefix("prefix_")
      c = a.removesuffix("_suffix")
    """)
    self.assertTypesMatchPytd(ty, """
      a : str
      b : str
      c : str
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
    """)
    self.assertTypesMatchPytd(ty, """
      b : bytearray
      x2 : bytearray
    """)

  def test_iter1(self):
    ty = self.Infer("""
      a = next(iter([1, 2, 3]))
      b = next(iter([1, 2, 3]), default = 4)
      c = next(iter([1, 2, 3]), "hello")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      a : int
      b : int
      c : Union[int, str]
    """)

  def test_dict_keys(self):
    ty = self.Infer("""
      m = {"x": None}
      a = m.keys() & {1, 2, 3}
      b = m.keys() - {1, 2, 3}
      c = m.keys() | {1, 2, 3}
      d = m.keys() ^ {1, 2, 3}
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict, Set, Union
      m : Dict[str, None]
      a : Set[str]
      b : Set[str]
      c : Set[Union[int, str]]
      d : Set[Union[int, str]]
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
      x1 = filter(None, bytearray(""))
      x2 = filter(None, (True, False))
      x3 = filter(None, {True, False})
      x4 = filter(f, {1: None}.keys())
      x5 = filter(None, {1: None}.keys())
      x6 = filter(re.compile("").search, ("",))
    """)
    self.assertTypesMatchPytd(ty, """
      import re
      from typing import Iterator
      def f(x: int) -> None: ...
      x1 : Iterator[int]
      x2 : Iterator[bool]
      x3 : Iterator[bool]
      x4 : Iterator[int]
      x5 : Iterator[int]
      x6 : Iterator[str]
      """)

  def test_filter_types(self):
    self.Check("""
      from typing import Iterator, List, Optional, Tuple, Union
      def f(xs: List[Optional[int]]) -> Iterator[int]:
        return filter(None, xs)
      def g(x: Tuple[int, str, None]) -> Iterator[Union[int, str]]:
        return filter(None, x)
    """)

  def test_zip(self):
    ty = self.Infer("""
      a = zip(())
      b = zip((1, 2j))
      c = zip((1, 2, 3), ())
      d = zip((), (1, 2, 3))
      e = zip((1j, 2j), (1, 2))
      assert zip([], [], [])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator, Tuple, Union
      a: zip[nothing]
      b: zip[Tuple[Union[int, complex]]]
      c: zip[nothing]
      d: zip[nothing]
      e: zip[Tuple[complex, int]]
      """)

  def test_dict(self):
    self.Check("""
      from typing import Dict, List, Union
      def t_testDict():
        d = {}
        d['a'] = 3
        d[3j] = 1.0
        assert_type(d, Dict[Union[complex, str], Union[float, int]])
        d2 = list(d.values())
        assert_type(d2, List[Union[float, int]])
        return d2[0]
      assert_type(t_testDict(), Union[float, int])
    """)

  def test_list_init(self):
    ty = self.Infer("""
      l3 = list({"a": 1}.keys())
      l4 = list({"a": 1}.values())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      l3 : List[str]
      l4 : List[int]
    """)

  def test_tuple_init(self):
    ty = self.Infer("""
      t3 = tuple({"a": 1}.keys())
      t4 = tuple({"a": 1}.values())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Tuple
      t3 : Tuple[str, ...]
      t4 : Tuple[int, ...]
    """)

  def test_items(self):
    ty = self.Infer("""
      lst = list({"a": 1}.items())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Tuple
      lst : List[Tuple[str, int]]
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
    self.assertTypesMatchPytd(ty, "v : bytes")

  def test_unicode_constant(self):
    ty = self.Infer("v = 'foo\\u00e4'")
    self.assertTypesMatchPytd(ty, "v : str")

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
      v1: memoryview
      v2: bytes
      v3: List[int]
      v4: str
    """)

  def test_bytes_hex(self):
    self.Check("""
      b = b'abc'
      b.hex(",", 3)
      m = memoryview(b)
      m.hex(",", 4)
      ba = bytearray([1,2,3])
      ba.hex(b",", 5)
    """)

  def test_memoryview_contextmanager(self):
    ty = self.Infer("""
      with memoryview(b'abc') as v:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      v : memoryview
    """)

  def test_array_tobytes(self):
    ty = self.Infer("""
      import array
      def t_testTobytes():
        return array.array('B').tobytes()
    """)
    self.assertTypesMatchPytd(ty, """
      import array
      def t_testTobytes() -> bytes: ...
    """)

  def test_iterator_builtins(self):
    ty = self.Infer("""
      v1 = map(int, ["0"])
      v2 = zip([0], [1])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Iterator, Tuple
      v1 : Iterator[int]
      v2 : zip[Tuple[int, int]]
    """)

  def test_next(self):
    ty = self.Infer("""
      itr = iter((1, 2))
      v1 = itr.__next__()
      v2 = next(itr)
    """)
    self.assertTypesMatchPytd(ty, """
      itr : tupleiterator[int]
      v1 : int
      v2 : int
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
      x1 : int
      x2 : Any
      y1 : int
      y2 : Any
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

  def test_breakpoint(self):
    self.Check("""
      breakpoint()
    """)

  def test_range_with_index(self):
    self.Check("""
      class C:
        def __index__(self) -> int:
          return 2
      range(C())
    """)

  def test_getitem_with_index(self):
    self.Check("""
      class C:
        def __index__(self) -> int:
          return 2
      x = [7, 8, 9]
      print(x[C()])
    """)

  def test_divmod(self):
    self.Check("""
      import datetime
      from typing import Tuple
      assert_type(divmod(1, 2), Tuple[int, int])
      assert_type(divmod(datetime.timedelta(1), datetime.timedelta(2)),
                  Tuple[int, datetime.timedelta])
    """)


class SetMethodsTest(test_base.BaseTest):
  """Tests for methods of the `set` class."""

  def test_union(self):
    self.Check("""
      from typing import Set, Union
      x: Set[int]
      y: Set[str]
      assert_type(x.union(y), Set[Union[int, str]])
      assert_type(set.union(x, y), Set[Union[int, str]])
    """)

  def test_difference(self):
    self.Check("""
      from typing import Set
      x: Set[int]
      assert_type(x.difference({None}), Set[int])
      assert_type(set.difference(x, {None}), Set[int])
    """)

  def test_intersection(self):
    self.Check("""
      from typing import Set
      x: Set[int]
      y: Set[str]
      assert_type(x.intersection(y), Set[int])
      assert_type(set.intersection(x, y), Set[int])
    """)

  def test_symmetric_difference(self):
    self.Check("""
      from typing import Set, Union
      x: Set[int]
      y: Set[str]
      assert_type(x.symmetric_difference(y), Set[Union[int, str]])
      assert_type(set.symmetric_difference(x, y), Set[Union[int, str]])
    """)

  def test_functools_reduce(self):
    # This is the functools.reduce type signature:
    # def reduce(
    #     function: Callable[[_T, _S], _T], sequence: Iterable[_S], initial: _T
    # ) -> _T: ...
    # `f1` does not error because the type used for `set.union` is
    # Callable[[Set[str], Iterable[str], Set[str]]], leading to the TypeVars in
    # reduce being filled in as _T=Set[str], _S=Iterable[str]. (Note that
    # Set[str] is treated as Set[Iterable[str]].)
    # `f2` errors because the type used for `set().union` is
    # Callable[[Iterable[str], Iterable[str]], Set[str]], leading to the
    # TypeVars being filled in as _T=Iterable[str] | Set[str], _S=Iterable[str].
    self.CheckWithErrors("""
      import functools
      from typing import Set
      def f1(x: Set[str]) -> Set[str]:
        return functools.reduce(set.union, x, set())
      def f2(x: Set[str]) -> Set[str]:
        return functools.reduce(set().union, x, set())  # bad-return-type
    """)


class TypesNoneTypeTest(test_base.BaseTest):
  """Tests for types.NoneType."""

  @test_utils.skipBeforePy((3, 10), "types.NoneType is new in 3.10")
  def test_function_param(self):
    self.Check("""
      import types
      def f(x: types.NoneType) -> None:
        return x
      f(None)
    """)

  @test_utils.skipBeforePy((3, 10), "types.NoneType is new in 3.10")
  def test_if_splitting(self):
    self.Check("""
      import types
      def f(x: types.NoneType) -> int:
        if x:
          return 'a'
        else:
          return 42
      a = f(None)
    """)


if __name__ == "__main__":
  test_base.main()
