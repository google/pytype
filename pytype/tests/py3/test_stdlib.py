"""Tests of selected stdlib functions."""

from pytype.tests import test_base
from pytype.tests import test_utils


class StrLibTestsBasic(test_base.TargetPython3BasicTest,
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

  def testSysVersionInfo(self):
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

  def test_async(self):
    """Test various asyncio features."""
    ty = self.Infer("""
      import asyncio
      def log(x: str):
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
      asyncio = ...  # type: module
      event_loop = ...  # type: asyncio.events.AbstractEventLoop
      class AsyncContextManager:
          def __aenter__(self) -> None: ...
          def __aexit__(self, exc_type, exc, tb) -> None: ...
      def log(x: str) -> str: ...
      def my_coroutine(seconds_to_sleep = ...) -> None: ...
      def test_with(x) -> None: ...
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
          pass
      async def iterate(x):
        async for i in x:
          pass
        else:
          pass
      iterate(AsyncIterable())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import NoReturn, TypeVar
      asyncio = ...  # type: module
      _TAsyncIterable = TypeVar('_TAsyncIterable', bound=AsyncIterable)
      class AsyncIterable:
          def __aiter__(self: _TAsyncIterable) -> _TAsyncIterable: ...
          def __anext__(self) -> NoReturn: ...
          def fetch_data(self) -> None: ...
      def iterate(x) -> None: ...
    """)

  def test_subprocess(self):
    # Test an attribute new in Python 3.
    self.Check("""
      import subprocess
      subprocess.run
    """)

  def test_enum(self):
    self.Check("""
      import enum
      class Foo(enum.Enum):
        foo = 0
      def f(x: Foo):
        pass
      f(Foo.foo)
    """)


test_base.main(globals(), __name__ == "__main__")
