"""Tests for coroutines."""

from pytype import file_utils
from pytype.tests import test_base


class GeneratorFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for coroutines."""

  def testRetTypeMatch(self):
    self.Check("""
      from typing import Any, Awaitable, Coroutine, List

      c: Coroutine[List[str], str, int] = None
      async def data() -> str:
        return 'data'

      def f1() -> Awaitable[str]:
        return data()

      def f2() -> Coroutine[Any, Any, str]:
        return data()

      def f3() -> Coroutine[List[str], str, int]:
        return c
    """)

  def testCoroutineTypeVarPyi(self):
    ty = self.Infer("""
      from typing import List, Coroutine, Any

      async def f() -> int:
        return 1

      c: Coroutine[Any, Any, int] = None
      c = f()
      x = c.send("str")
      async def bar():
        x = await c
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine

      c: Coroutine[Any, Any, int]
      x: Any

      def bar() -> Coroutine[Any, Any, int]: ...
      def f() -> Coroutine[Any, Any, int]: ...
    """)

  def testNativeCoroutinePyi(self):
    ty = self.Infer("""
      async def callee():
        if __random__:
          return 1
        else:
          return "str"

      async def caller():
        x = await callee()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Union, Coroutine

      def callee() -> Coroutine[Any, Any, Union[int, str]]: ...
      def caller() -> Coroutine[Any, Any, Union[int, str]]: ...
    """)

  def testNativeCoroutineError(self):
    errors = self.CheckWithErrors("""\
      async def f1() -> str:
        return 1

      async def f2() -> int:
        return 1

      async def f3():
        return 1

      def f4(x: str):
        pass

      async def caller():
        f4(await f1())
        f4(await f2())
        f4(await f3())
    """)
    self.assertErrorLogIs(errors, [
        (2, "bad-return-type", r"str.*int"),
        (15, "wrong-arg-types", r"str.*int"),
        (16, "wrong-arg-types", r"str.*int")])

  def testGeneratorBasedCoroutinePyi(self):
    ty = self.Infer("""
      import asyncio
      import types

      @asyncio.coroutine
      def f1():
        yield from asyncio.sleep(1)

      async def f2():
        await asyncio.sleep(1)

      @types.coroutine
      def f3():
        yield 1
        yield from asyncio.sleep(1)
        if __random__:
          return 1
        else:
          return "str"

      async def caller():
        await f1()
        await f2()
        x = await f3()
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine, Union

      asyncio: module
      types: module

      def caller() -> Coroutine[Any, Any, Union[int, str]]: ...
      def f1() -> Coroutine[Any, Any, None]: ...
      def f2() -> Coroutine[Any, Any, None]: ...
      def f3() -> Coroutine[Any, Any, Union[int, str]]: ...
    """)

  def testGeneratorBasedCoroutineError(self):
    errors = self.CheckWithErrors("""\
      from typing import Generator
      import types

      @types.coroutine
      def f1():
        return 1

      @types.coroutine
      def f2() -> Generator[int, None, int]:
        yield 1
        return 1

      def f3(x, y: str):
        pass

      async def caller():
        x = await f1()
        y = await f2()
        f3(x, y)
    """)
    self.assertErrorLogIs(errors, [
        (17, "bad-return-type", r"Awaitable.*int"),
        (19, "wrong-arg-types", r"y: str.*y: int")])

  def testAwaitablePyi(self):
    ty = self.Infer("""
      from typing import Awaitable, Generator
      import types

      class BaseAwaitable(object):
        def __iter__(self):
          return self

        __await__ = __iter__

      class SubAwaitable(BaseAwaitable):
        pass

      async def c1() -> int:
        return 123

      @types.coroutine
      def c2() -> Generator[int, None, int]:
        yield 1
        return 123

      async def f1():
        x = await BaseAwaitable()
        y = await SubAwaitable()

      async def f2(x: Awaitable[int]):
        return await x

      async def f3():
        await f2(BaseAwaitable())
        await f2(SubAwaitable())
        await f2(c1())
        await f2(c2())
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Awaitable, Coroutine, TypeVar

      types: module

      _TBaseAwaitable = TypeVar('_TBaseAwaitable', bound=BaseAwaitable)

      class BaseAwaitable(object):
          def __await__(self: _TBaseAwaitable) -> _TBaseAwaitable: ...
          def __iter__(self: _TBaseAwaitable) -> _TBaseAwaitable: ...

      class SubAwaitable(BaseAwaitable):
          pass


      def c1() -> Coroutine[Any, Any, int]: ...
      def c2() -> Coroutine[Any, Any, int]: ...
      def f1() -> Coroutine[Any, Any, None]: ...
      def f2(x: Awaitable[int]) -> Coroutine[Any, Any, int]: ...
      def f3() -> Coroutine[Any, Any, None]: ...
    """)

  def testInvalidAwaitable(self):
    errors = self.CheckWithErrors("""\
      class A(object):
        pass

      async def fun():
        await A()
    """)
    self.assertErrorLogIs(errors, [
        (5, "bad-return-type", r"Awaitable.*A")])

  def testAsyncForPyi(self):
    ty = self.Infer("""
      class MyIter(object):
        def __aiter__(self):
          return self

        async def __anext__(self):
          if __random__:
            if __random__:
              return 1
            else:
              return "str"
          else:
            raise StopAsyncIteration

      async def caller():
        res = []
        async for i in MyIter():
          res.append(i)
        else:
          pass
        return res
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine, List, TypeVar, Union

      _TMyIter = TypeVar('_TMyIter', bound=MyIter)

      class MyIter(object):
          def __aiter__(self: _TMyIter) -> _TMyIter: ...
          def __anext__(self) -> Coroutine[Any, Any, Union[int, str]]: ...


      def caller() -> Coroutine[Any, Any, List[Union[int, str]]]: ...
    """)

  def testAsyncForError(self):
    errors = self.CheckWithErrors("""\
      class Iter1(object):
        pass

      class Iter2(object):
        def __aiter__(self):
          return self

      class Iter3(object):
        def __aiter__(self):
          return self

        def __anext__(self):
          if __random__:
            if __random__:
              return 1
            else:
              return "str"
          else:
            raise StopAsyncIteration

      class Iter4(object):
        def __aiter__(self):
          return self

        async def __anext__(self):
          if __random__:
            if __random__:
              return 1
            else:
              return "str"
          else:
            raise StopAsyncIteration

      async def caller():
        res = []
        async for i in Iter1():
          res.append(i)
        async for i in Iter2():
          res.append(i)
        async for i in Iter3():
          res.append(i)
        async for i in Iter4():
          res.append(i)
        return res
    """)
    self.assertErrorLogIs(errors, [
        (36, "attribute-error", r"No attribute.*__aiter__"),
        (38, "attribute-error", r"No attribute.*__anext__"),
        (40, "bad-return-type", r"Awaitable.*Union\[int, str]"),
    ])

  def testAsyncWithPyi(self):
    ty = self.Infer("""
      async def log(s):
        return s

      class AsyncCtx(object):
        async def __aenter__(self):
          await log("__aenter__")
          return self

        async def __aexit__(self, exc_type, exc, tb):
          await log("__aexit__")

        def func():
          pass

      def fctx(x: AsyncCtx):
        pass

      async def caller():
        async with AsyncCtx() as var:
          var.func()
          fctx(var)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine, TypeVar

      _T0 = TypeVar('_T0')

      class AsyncCtx(object):
          def __aenter__(self) -> Coroutine[Any, Any, AsyncCtx]: ...
          def __aexit__(self, exc_type, exc, tb) -> Coroutine[Any, Any, None]: ...
          def func() -> None: ...


      def caller() -> Coroutine[Any, Any, None]: ...
      def fctx(x: AsyncCtx) -> None: ...
      def log(s: _T0) -> Coroutine[Any, Any, _T0]: ...
    """)

  def testAsyncWithError(self):
    errors = self.CheckWithErrors("""\
      class AsyncCtx1(object):
        pass

      class AsyncCtx2(object):
        def __aenter__(self):
          return self

        def __aexit__(self, exc_type, exc, tb):
          return "str"

      async def caller():
        async with AsyncCtx1() as var1, AsyncCtx2() as var2:
          pass
    """)
    self.assertErrorLogIs(errors, [
        (12, "attribute-error", r"No attribute.*__aexit__"),
        (12, "attribute-error", r"No attribute.*__aenter__"),
        (12, "bad-return-type", r"Awaitable.*AsyncCtx2"),
        (13, "bad-return-type", r"Awaitable.*str"),
    ])

  def testLoadPyi(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any, Coroutine, Awaitable, TypeVar

        def f1() -> Coroutine[Any, Any, str]: ...
        def f2() -> Awaitable[str]: ...

        _TBaseAwaitable = TypeVar('_TBaseAwaitable', bound=BaseAwaitable)

        class BaseAwaitable(object):
          def __await__(self: _TBaseAwaitable) -> _TBaseAwaitable: ...
          def __iter__(self: _TBaseAwaitable) -> _TBaseAwaitable: ...


        class SubAwaitable(BaseAwaitable):
          pass


        class MyIter(object):
          def __aiter__(self) -> MyIter: ...
          def __anext__(self) -> Coroutine[Any, Any, str]: ...


        class AsyncCtx(object):
          def __aenter__(self) -> Coroutine[Any, Any, AsyncCtx]: ...
          def __aexit__(self, exc_type, exc, tb) -> Coroutine[Any, Any, None]: ...
          def func() -> None: ...
      """)
      ty = self.Infer("""
        import foo
        from typing import Awaitable, Coroutine, Any

        async def func1(x: Awaitable[str]):
          res = []
          await foo.BaseAwaitable()
          await foo.SubAwaitable()
          res.append(await foo.f1())
          res.append(await foo.f2())
          res.append(await x)
          async for i in foo.MyIter():
            res.append(i)
          async with foo.AsyncCtx() as var:
            var.func()
          return res

        async def func2(x: Coroutine[Any, Any, str]):
          res = []
          await foo.BaseAwaitable()
          await foo.SubAwaitable()
          res.append(await foo.f1())
          res.append(await foo.f2())
          res.append(await x)
          async for i in foo.MyIter():
            res.append(i)
          async with foo.AsyncCtx() as var:
            var.func()
          return res

        func1(foo.f1())
        func1(foo.f2())
        func2(foo.f1())
      """, deep=True, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any, Awaitable, Coroutine, List

        foo: module

        def func1(x: Awaitable[str]) -> Coroutine[Any, Any, List[str]]: ...
        def func2(x: Coroutine[Any, Any, str]) -> Coroutine[Any, Any, List[str]]: ...
      """)

  def testAwaitVariableWithMulitBindings(self):
    ty = self.Infer("""
      async def f1():
        return 123

      async def f2():
        return "str"

      async def caller():
        if __random__:
          x = f1()
        else:
          x = f2()
        return await x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine, Union

      def caller() -> Coroutine[Any, Any, Union[int, str]]: ...
      def f1() -> Coroutine[Any, Any, int]: ...
      def f2() -> Coroutine[Any, Any, str]: ...
    """)

  def testAwaitGenerator(self):
    ty = self.Infer("""
      import asyncio

      async def tcp_echo_client(message):
        return await asyncio.open_connection( '127.0.0.1', 8888)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine, Tuple
      asyncio: module
      def tcp_echo_client(message) -> Coroutine[
        Any, Any,
        Tuple[asyncio.streams.StreamReader, asyncio.streams.StreamWriter]]: ...
    """)

  def testQueue(self):
    ty = self.Infer("""
      import asyncio

      async def worker(queue):
        return await queue.get()

      async def main():
        queue = asyncio.Queue()
        worker(queue)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Coroutine
      asyncio: module
      def worker(queue) -> coroutine: ...
      def main() -> Coroutine[Any, Any, None]: ...
    """)

  def testFuture(self):
    ty = self.Infer("""
      import asyncio

      async def foo() -> int:
        return 1

      async def call_foo():
        for future in asyncio.as_completed([foo()]):
          return await future
    """)
    self.assertTypesMatchPytd(ty, """
      import asyncio.futures
      from typing import Any, Coroutine, Optional
      asyncio: module
      def foo() -> Coroutine[Any, Any, int]: ...
      def call_foo() -> Coroutine[Any, Any, Optional[int]]: ...
    """)


test_base.main(globals(), __name__ == "__main__")
