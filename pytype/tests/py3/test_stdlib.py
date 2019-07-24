"""Tests of selected stdlib functions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class StdLibTestsBasic(test_base.TargetPython3BasicTest,
                       test_utils.TestCollectionsMixin):
  """Tests for files in typeshed/stdlib."""

  def testCollectionsDeque(self):
    # This method is different from the preceding ones because we model
    # collections.deque as a subclass, rather than an alias, of typing.Deque.
    errors = self.CheckWithErrors("""\
      from typing import Deque
      import collections
      def f1(x: Deque): ...
      def f2(x: int): ...
      f1(collections.deque())
      f2(collections.deque())  # line 6
    """)
    self.assertErrorLogIs(errors, [(6, "wrong-arg-types", r"int.*deque")])

  def testCollectionsDequeInit(self):
    ty = self.Infer("""\
      import collections
      x = collections.deque([1, 2, 3], maxlen=10)
    """)
    self.assertTypesMatchPytd(ty, """
      collections = ...  # type: module
      x = ...  # type: collections.deque[int]
    """)

  def testPartial(self):
    self.Check("""\
      import functools
      from typing import TypeVar
      T = TypeVar('T', float, str)
      def identity(x: T) -> T: return x
      functools.partial(identity)
    """)

  def testCollectionsContainer(self):
    self._testCollectionsObject("Container", "[]", "42", r"Container.*int")

  def testCollectionsHashable(self):
    self._testCollectionsObject("Hashable", "42", "[]", r"Hashable.*List")

  def testCollectionsIterable(self):
    self._testCollectionsObject("Iterable", "[]", "42", r"Iterable.*int")

  def testCollectionsIterator(self):
    self._testCollectionsObject("Iterator", "iter([])", "42", r"Iterator.*int")

  def testCollectionsSized(self):
    self._testCollectionsObject("Sized", "[]", "42", r"Sized.*int")

  def testCollectionsCallable(self):
    self._testCollectionsObject("Callable", "list", "42", r"Callable.*int")

  def testCollectionsSequence(self):
    self._testCollectionsObject("Sequence", "[]", "42", r"Sequence.*int")

  def testCollectionsMutableSequence(self):
    self._testCollectionsObject(
        "MutableSequence", "[]", "42", r"MutableSequence.*int")

  def testCollectionsSet(self):
    self._testCollectionsObject("Set", "set()", "42", r"set.*int")

  def testCollectionsMutableSet(self):
    self._testCollectionsObject("MutableSet", "set()", "42", r"MutableSet.*int")

  def testCollectionsMapping(self):
    self._testCollectionsObject("Mapping", "{}", "42", r"Mapping.*int")

  def testCollectionsMutableMapping(self):
    self._testCollectionsObject(
        "MutableMapping", "{}", "42", r"MutableMapping.*int")


class StdlibTestsFeatures(test_base.TargetPython3FeatureTest,
                          test_utils.TestCollectionsMixin):
  """Tests for files in typeshed/stdlib."""

  def testCollectionsSmokeTest(self):
    # These classes are not fully implemented in typing.py.
    self.Check("""
      import collections
      collections.AsyncIterable
      collections.AsyncIterator
      collections.AsyncGenerator
      collections.Awaitable
      collections.Coroutine
    """)

  def testCollectionsByteString(self):
    self._testCollectionsObject("ByteString", "b'hello'", "42",
                                r"ByteString.*int")

  def testCollectionsCollection(self):
    self._testCollectionsObject("Collection", "[]", "42", r"Collection.*int")

  def testCollectionsGenerator(self):
    self._testCollectionsObject("Generator", "i for i in range(42)", "42",
                                r"generator.*int")

  def testCollectionsReversible(self):
    self._testCollectionsObject("Reversible", "[]", "42", r"Reversible.*int")

  def testCollectionsMappingView(self):
    self._testCollectionsObject(
        "MappingView", "{}.items()", "42", r"MappingView.*int")

  def testCollectionsItemsView(self):
    self._testCollectionsObject(
        "ItemsView", "{}.items()", "42", r"ItemsView.*int")

  def testCollectionsKeysView(self):
    self._testCollectionsObject(
        "KeysView", "{}.keys()", "42", r"KeysView.*int")

  def testCollectionsValuesView(self):
    self._testCollectionsObject(
        "ValuesView", "{}.values()", "42", r"ValuesView.*int")

  def testTempfile(self):
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
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union
      import typing
      os = ...  # type: module
      tempfile = ...  # type: module
      typing = ...  # type: module
      def f(fi: typing.IO) -> Union[bytes, str]: ...
    """)

  def testDefaultDict(self):
    self.Check("""\
      import collections
      import itertools
      ids = collections.defaultdict(itertools.count(17).__next__)
    """)

  def testDefaultDictMatchesDict(self):
    self.Check("""
      import collections
      from typing import DefaultDict, Dict
      def take_dict(d: Dict[int, str]): pass
      def take_defaultdict(d: DefaultDict[int, str]): pass
      d = collections.defaultdict(str, {1: "hello"})
      take_dict(d)
      take_defaultdict(d)
    """)

  def testSysVersionInfoLt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] < 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: str
    """)

  def testSysVersionInfoLe(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] <= 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoEq(self):
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
      sys = ...  # type: module
      v = ...  # type: str
    """)

  def testSysVersionInfoGe(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] >= 3:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoGt(self):
    ty = self.Infer("""
      import sys
      if sys.version_info[0] > 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys = ...  # type: module
      v = ...  # type: int
    """)

  def testSysVersionInfoNamedAttribute(self):
    ty = self.Infer("""
      import sys
      if sys.version_info.major == 2:
        v = 42
      else:
        v = "hello world"
    """)
    self.assertTypesMatchPytd(ty, """
      sys: module
      v: str
    """)

  @test_utils.skipIn37("https://github.com/google/pytype/issues/203")
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
      import asyncio.events
      from typing import Any, Coroutine

      asyncio: module
      event_loop: asyncio.events.AbstractEventLoop

      class AsyncContextManager:
          def __aenter__(self) -> Coroutine[Any, Any, None]: ...
          def __aexit__(self, exc_type, exc, tb) -> Coroutine[Any, Any, None]: ...
      def log(x: str) -> Coroutine[Any, Any, str]: ...
      def my_coroutine(seconds_to_sleep = ...) -> Coroutine[Any, Any, None]: ...
      def test_with(x) -> Coroutine[Any, Any, None]: ...
    """)

  @test_utils.skipIn37("https://github.com/google/pytype/issues/203")
  def test_async_iter(self):
    ty = self.Infer("""
      import asyncio
      class AsyncIterable:
        async def __aiter__(self):
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
      from typing import Any, Coroutine
      asyncio: module
      class AsyncIterable:
          def __aiter__(self) -> Coroutine[Any, Any, AsyncIterable]: ...
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
      subprocess: module
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
      subprocess: module
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
      subprocess: module
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
      subprocess: module
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
      subprocess: module
      def run(cmd) -> str: ...
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
      from typing import ChainMap, List, Mapping, Union
      collections: module
      v1: ChainMap[Union[bytes, str], Union[int, str]]
      v2: List[Mapping[Union[bytes, str], Union[int, str]]]
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
      from typing import Match, Optional, Pattern
      re: module
      pattern: Pattern[str]
      match: Optional[Match[str]]
      group: str
    """)

  def test_textio_buffer(self):
    self.Check("""
      import sys
      sys.stdout.buffer
    """)


test_base.main(globals(), __name__ == "__main__")
