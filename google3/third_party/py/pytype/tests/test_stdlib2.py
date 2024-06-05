"""Tests of selected stdlib functions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class StdLibTestsBasic(test_base.BaseTest,
                       test_utils.TestCollectionsMixin):
  """Tests for files in typeshed/stdlib."""

  def test_collections_deque(self):
    # This method is different from the preceding ones because we model
    # collections.deque as a subclass, rather than an alias, of typing.Deque.
    errors = self.CheckWithErrors("""
      from typing import Deque
      import collections
      def f1(x: Deque): ...
      def f2(x: int): ...
      f1(collections.deque())
      f2(collections.deque())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*deque"})

  def test_collections_deque_init(self):
    ty = self.Infer("""
      import collections
      x = collections.deque([1, 2, 3], maxlen=10)
    """)
    self.assertTypesMatchPytd(ty, """
      import collections
      x = ...  # type: collections.deque[int]
    """)

  def test_partial(self):
    self.Check("""
      import functools
      from typing import TypeVar
      T = TypeVar('T', float, str)
      def identity(x: T) -> T: return x
      functools.partial(identity)
    """)

  def test_collections_container(self):
    self._testCollectionsObject("Container", "[]", "42", r"Container.*int")

  def test_collections_hashable(self):
    self._testCollectionsObject("Hashable", "42", "[]", r"Hashable.*List")

  def test_collections_iterable(self):
    self._testCollectionsObject("Iterable", "[]", "42", r"Iterable.*int")

  def test_collections_iterator(self):
    self._testCollectionsObject("Iterator", "iter([])", "42", r"Iterator.*int")

  def test_collections_sized(self):
    self._testCollectionsObject("Sized", "[]", "42", r"Sized.*int")

  def test_collections_callable(self):
    self._testCollectionsObject("Callable", "list", "42", r"Callable.*int")

  def test_collections_sequence(self):
    self._testCollectionsObject("Sequence", "[]", "42", r"Sequence.*int")

  def test_collections_mutable_sequence(self):
    self._testCollectionsObject(
        "MutableSequence", "[]", "42", r"MutableSequence.*int")

  def test_collections_set(self):
    self._testCollectionsObject("Set", "set()", "42", r"set.*int")

  def test_collections_mutable_set(self):
    self._testCollectionsObject("MutableSet", "set()", "42", r"MutableSet.*int")

  def test_collections_mapping(self):
    self._testCollectionsObject("Mapping", "{}", "42", r"Mapping.*int")

  def test_collections_mutable_mapping(self):
    self._testCollectionsObject(
        "MutableMapping", "{}", "42", r"MutableMapping.*int")

  def test_tempdir_name(self):
    self.Check("""
      import tempfile
      def f() -> str:
        return tempfile.TemporaryDirectory().name
    """)

  def test_fraction_subclass(self):
    ty = self.Infer("""
      import fractions
      class MyClass(fractions.Fraction):
        pass
      def foo() -> MyClass:
        return MyClass(1, 2)
    """)
    self.assertTypesMatchPytd(ty, """
      import fractions
      class MyClass(fractions.Fraction): ...
      def foo() -> MyClass: ...
  """)

  def test_codetype(self):
    self.Check("""
      import types
      class Foo:
        x: types.CodeType
        def set_x(self):
          self.x = compile('', '', '')
    """)

  def test_os_path_basename(self):
    self.options.tweak(strict_parameter_checks=False)
    self.Check("""
      import os
      from typing import Optional
      x: Optional[str]
      assert_type(os.path.basename(x), str)
    """)

  def test_decimal_round(self):
    self.Check("""
      import decimal
      x = decimal.Decimal('5.02')
      assert_type(round(x), int)
      assert_type(round(x, 1), decimal.Decimal)
    """)


class StdlibTestsFeatures(test_base.BaseTest,
                          test_utils.TestCollectionsMixin):
  """Tests for files in typeshed/stdlib."""

  def test_collections_smoke_test(self):
    # These classes are not fully implemented in typing.py.
    self.Check("""
      import collections
      collections.AsyncIterable
      collections.AsyncIterator
      collections.AsyncGenerator
      collections.Awaitable
      collections.Coroutine
    """)

  def test_collections_bytestring(self):
    self._testCollectionsObject("ByteString", "b'hello'", "42",
                                r"Union\[bytearray, bytes, memoryview\].*int")

  def test_collections_collection(self):
    self._testCollectionsObject("Collection", "[]", "42", r"Collection.*int")

  def test_collections_generator(self):
    self._testCollectionsObject("Generator", "i for i in range(42)", "42",
                                r"generator.*int")

  def test_collections_reversible(self):
    self._testCollectionsObject("Reversible", "[]", "42", r"Reversible.*int")

  def test_collections_mapping_view(self):
    self._testCollectionsObject(
        "MappingView", "{}.items()", "42", r"MappingView.*int")

  def test_collections_items_view(self):
    self._testCollectionsObject(
        "ItemsView", "{}.items()", "42", r"ItemsView.*int")

  def test_collections_keys_view(self):
    self._testCollectionsObject(
        "KeysView", "{}.keys()", "42", r"KeysView.*int")

  def test_collections_values_view(self):
    self._testCollectionsObject(
        "ValuesView", "{}.values()", "42", r"ValuesView.*int")

  def test_tempfile(self):
    # TODO(b/63407497): Enabling --strict_parameter_checks leads to a bunch of
    # str vs bytes wrong-arg-types errors.
    self.options.tweak(strict_parameter_checks=False)
    ty = self.Infer("""
      import tempfile
      import typing
      import os
      def f(fi: typing.IO):
        fi.write("foobar")
        pos = fi.tell()
        fi.seek(0, os.SEEK_SET)
        s = fi.read(6)
        fi.close()
        return s
      f(tempfile.TemporaryFile("wb", suffix=".foo"))
      f(tempfile.NamedTemporaryFile("wb", suffix=".foo"))
      f(tempfile.SpooledTemporaryFile(1048576, "wb", suffix=".foo"))
    """)
    self.assertTypesMatchPytd(ty, """
      import os
      import tempfile
      import typing
      from typing import Any, Union
      def f(fi: typing.IO) -> Union[bytes, str]: ...
    """)

  def test_defaultdict(self):
    self.Check("""
      import collections
      import itertools
      ids = collections.defaultdict(itertools.count(17).__next__)
    """)

  def test_defaultdict_matches_dict(self):
    self.Check("""
      import collections
      from typing import DefaultDict, Dict
      def take_dict(d: Dict[int, str]): pass
      def take_defaultdict(d: DefaultDict[int, str]): pass
      d = collections.defaultdict(str, {1: "hello"})
      take_dict(d)
      take_defaultdict(d)
    """)

  def test_defaultdict_kwargs(self):
    self.Check("""
      import collections
      from typing import DefaultDict, Union
      def take_str_int_values(d: DefaultDict[str, Union[str, int]]): pass
      d = collections.defaultdict(str, {'x': 'x'}, an_int = 1)
      take_str_int_values(d)
      def take_three_types(d: DefaultDict[str, Union[str, int, list]]): pass
      e = collections.defaultdict(str, {'x': [1, 2]}, an_int = 3)
      take_three_types(e)
      collections.defaultdict(None, [(1, '2'), (3, '4')], a=1, b=2)
    """)

  def test_sys_version_info_lt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] < 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v = ...  # type: str
    """)

  def test_sys_version_info_le(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] <= 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v = ...  # type: int
    """)

  def test_sys_version_info_eq(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] == 2:
        v = 42
      elif sys.version_info[0] == 3:
        v = "hello world"
      else:
        v = None
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v = ...  # type: str
    """)

  def test_sys_version_info_ge(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] >= 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v = ...  # type: int
    """)

  def test_sys_version_info_gt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] > 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v = ...  # type: int
    """)

  def test_sys_version_info_named_attribute(self):
    ty = self.Infer("""
      import sys
      if sys.version_info.major == 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v: str
    """)

  def test_sys_version_info_tuple(self):
    ty = self.Infer("""
      import sys
      if sys.version_info >= (3, 5):
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v: int
    """)

  def test_sys_version_info_slice(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[:2] >= (3, 5):
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      v: int
    """)

  def test_sys_platform(self):
    self.options.tweak(platform="linux")
    ty = self.Infer("""
      import sys
      if sys.platform == "linux":
        x = 0
      else:
        x = "0"
    """)
    self.assertTypesMatchPytd(ty, """
      import sys
      x: int
    """)

  def test_async(self):
    """Test various asyncio features."""
    ty = self.Infer("""
      import asyncio
      async def log(x: str):
        return x
      class AsyncContextManager:
        async def __aenter__(self):
          await log("entering context")
        async def __aexit__(self, exc_type, exc, tb):
          await log("exiting context")
      async def my_coroutine(seconds_to_sleep=0.4):
          await asyncio.sleep(seconds_to_sleep)
      async def test_with(x):
        try:
          async with x as y:
            pass
        finally:
          pass
      event_loop = asyncio.get_event_loop()
      try:
        event_loop.run_until_complete(my_coroutine())
      finally:
        event_loop.close()
    """)
    self.assertTypesMatchPytd(ty, """
      import asyncio
      from typing import Any, Coroutine

      event_loop: asyncio.events.AbstractEventLoop

      class AsyncContextManager:
          def __aenter__(self) -> Coroutine[Any, Any, None]: ...
          def __aexit__(self, exc_type, exc, tb) -> Coroutine[Any, Any, None]: ...
      def log(x: str) -> Coroutine[Any, Any, str]: ...
      def my_coroutine(seconds_to_sleep = ...) -> Coroutine[Any, Any, None]: ...
      def test_with(x) -> Coroutine[Any, Any, None]: ...
    """)

  def test_async_iter(self):
    ty = self.Infer("""
      import asyncio
      class AsyncIterable:
        def __aiter__(self):
          return self
        async def __anext__(self):
          data = await self.fetch_data()
          if data:
            return data
          else:
            raise StopAsyncIteration
        async def fetch_data(self):
          return 1
      async def iterate(x):
        async for i in x:
          pass
        else:
          pass
      iterate(AsyncIterable())
    """)
    self.assertTypesMatchPytd(ty, """
      import asyncio
      from typing import Any, Coroutine, TypeVar
      _TAsyncIterable = TypeVar('_TAsyncIterable', bound=AsyncIterable)
      class AsyncIterable:
          def __aiter__(self: _TAsyncIterable) -> _TAsyncIterable: ...
          def __anext__(self) -> Coroutine[Any, Any, int]: ...
          def fetch_data(self) -> Coroutine[Any, Any, int]: ...
      def iterate(x) -> Coroutine[Any, Any, None]: ...
    """)

  def test_subprocess(self):
    # Test an attribute new in Python 3.
    self.Check("""
      import subprocess
      subprocess.run
    """)

  def test_popen_bytes(self):
    ty = self.Infer("""
      import subprocess
      def run(cmd):
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      def run(cmd) -> bytes: ...
    """)

  def test_popen_bytes_no_encoding(self):
    ty = self.Infer("""
      import subprocess
      def run(cmd):
        proc = subprocess.Popen(cmd, encoding=None, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      def run(cmd) -> bytes: ...
    """)

  def test_popen_bytes_no_universal_newlines(self):
    ty = self.Infer("""
      import subprocess
      def run(cmd):
        proc = subprocess.Popen(
            cmd, universal_newlines=False, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      def run(cmd) -> bytes: ...
    """)

  def test_popen_str_encoding(self):
    ty = self.Infer("""
      import subprocess
      def run(cmd):
        proc = subprocess.Popen(cmd, encoding='utf-8', stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      def run(cmd) -> str: ...
    """)

  def test_popen_str_universal_newlines(self):
    ty = self.Infer("""
      import subprocess
      def run(cmd):
        proc = subprocess.Popen(
            cmd, universal_newlines=True, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      def run(cmd) -> str: ...
    """)

  def test_popen_ambiguous_universal_newlines(self):
    ty = self.Infer("""
      import subprocess
      from typing import Any
      def run1(value: bool):
        proc = subprocess.Popen(['ls'], universal_newlines=value)
        stdout, _ = proc.communicate()
        return stdout
      def run2(value: Any):
        proc = subprocess.Popen(['ls'], universal_newlines=value)
        stdout, _ = proc.communicate()
        return stdout
    """)
    self.assertTypesMatchPytd(ty, """
      import subprocess
      from typing import Any
      def run1(value: bool) -> Any: ...
      def run2(value: Any) -> Any: ...
    """)

  def test_popen_kwargs(self):
    self.Check("""
      import subprocess
      def popen(cmd: str, **kwargs):
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
        process = subprocess.Popen(cmd, **kwargs)
        stdout, _ = process.communicate()
        assert_type(stdout, 'Any')
    """)

  def test_enum(self):
    self.Check("""
      import enum
      class Foo(enum.Enum):
        foo = 0
        bar = enum.auto()
      def f(x: Foo):
        pass
      f(Foo.foo)
    """)

  def test_contextlib(self):
    self.Check("from contextlib import AbstractContextManager")

  def test_chainmap(self):
    ty = self.Infer("""
      import collections
      v1 = collections.ChainMap({'a': 'b'}, {b'c': 0})
      v2 = v1.maps
      v3 = v1.parents
      v4 = v1.new_child()
    """)
    self.assertTypesMatchPytd(ty, """
      import collections
      from typing import ChainMap, List, MutableMapping, Union
      v1: ChainMap[Union[bytes, str], Union[int, str]]
      v2: List[MutableMapping[Union[bytes, str], Union[int, str]]]
      v3: ChainMap[Union[bytes, str], Union[int, str]]
      v4: ChainMap[Union[bytes, str], Union[int, str]]
    """)

  def test_re(self):
    ty = self.Infer("""
      import re
      pattern = re.compile('')
      match = pattern.fullmatch('')
      if match:
        group = match[0]
    """)
    self.assertTypesMatchPytd(ty, """
      import re
      from typing import Optional
      pattern: re.Pattern[str]
      match: Optional[re.Match[str]]
      group: str
    """)

  def test_textio_buffer(self):
    self.Check("""
      import sys
      sys.stdout.buffer
    """)

  def test_io_open(self):
    ty = self.Infer("""
      import io
      def f(name):
        return io.open(name, "rb").read()
    """)
    self.assertTypesMatchPytd(ty, """
      import io
      def f(name) -> bytes: ...
    """)

  def test_array_frombytes(self):
    self.Check("""
      import array
      def f(x: array.array, y: bytes):
        return x.frombytes(y)
    """)

  def test_property_attributes(self):
    self.Check("""
      class C:
        @property
        def x(self):
          pass
      print(C.x.fget, C.x.fset, C.x.fdel)
    """)

  def test_re_and_typing(self):
    self.CheckWithErrors("""
      import re
      from typing import Match, Optional, Pattern

      ok1: Pattern = re.compile("")
      ok2: Optional[Match] = re.match("", "")

      no1: Pattern = 0  # annotation-type-mismatch
      no2: Match = 0  # annotation-type-mismatch
    """)

  def test_contextmanager_keywordonly(self):
    ty = self.Infer("""
      from contextlib import contextmanager
      @contextmanager
      def myctx(*, msg=None):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Iterator, ParamSpec, TypeVar
      _P = ParamSpec('_P')
      _T_co = TypeVar('_T_co')
      def contextmanager(
          func: Callable[_P, Iterator[_T_co]]
      ) -> Callable[_P, contextlib._GeneratorContextManager[_T_co]]: ...
      def myctx(*, msg = ...) -> contextlib._GeneratorContextManager: ...
    """)


if __name__ == "__main__":
  test_base.main()
