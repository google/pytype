"""Tests for async generators."""

from pytype.tests import test_base
from pytype.tests import test_utils


class AsyncGeneratorFeatureTest(test_base.BaseTest):
  """Tests for async iterable, iterator, context manager, generator."""

  def test_empty_annotation(self):
    self.Check("""
      from typing import AsyncIterator, AsyncIterable, AsyncGenerator
      async def f() -> AsyncIterator:
        yield 5

      async def f() -> AsyncIterable:
        yield 5

      async def f() -> AsyncGenerator:
        yield 5
    """)

  def test_union_annotation(self):
    self.Check("""
      from typing import AsyncGenerator, AsyncIterator, AsyncIterable, Union

      async def f() -> Union[AsyncGenerator, AsyncIterator, AsyncIterable]:
        yield 5
    """)

  def test_annotation_with_type(self):
    self.Check("""
      from typing import AsyncGenerator, AsyncIterator, AsyncIterable

      async def gen1() -> AsyncGenerator[int, int]:
        yield 1

      async def gen2() -> AsyncIterator[int]:
        yield 1

      async def gen3() -> AsyncIterable[int]:
        yield 1
    """)

  def test_yield_type_infer(self):
    ty = self.Infer("""
      async def f(x):
        if x == 1:
          yield 1
        else:
          yield "1"

      x = f(2)
      y = f(1)

      async def func():
        return "str"

      async def gen():
        l = [1, 2, 3]
        for x in l:
          yield x
        x = await func()
        yield x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, AsyncGenerator, Coroutine, Union

      x: AsyncGenerator[str, Any]
      y: AsyncGenerator[int, Any]

      def f(x) -> AsyncGenerator[Union[int, str], Any]: ...
      def func() -> Coroutine[Any, Any, str]: ...
      def gen() -> AsyncGenerator[Union[int, str], Any]: ...
    """,
    )

  def test_annotation_error(self):
    errors = self.CheckWithErrors("""
      from typing import AsyncGenerator, AsyncIterator, AsyncIterable, Any, Union

      async def gen1() -> AsyncGenerator[bool, int]:
        yield 1  # bad-return-type[e1]

      async def gen2() -> AsyncIterator[bool]:
        yield 1  # bad-return-type[e2]

      async def gen3() -> AsyncIterable[bool]:
        yield 1  # bad-return-type[e3]

      async def gen4() -> int:  # bad-yield-annotation[e4]
        yield 1

      async def fun():
        g = gen1()
        await g.asend("str")  # wrong-arg-types[e5]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"bool.*int",
            "e2": r"bool.*int",
            "e3": r"bool.*int",
            "e4": r"AsyncGenerator.*AsyncIterable.*AsyncIterator",
            "e5": r"int.*str",
        },
    )

  def test_match_base_class_error(self):
    errors = self.CheckWithErrors("""
      from typing import AsyncGenerator, AsyncIterator, AsyncIterable, Union, Any

      async def func():
        return "str"

      async def gen() -> AsyncGenerator[Union[int, str], Any]:
        l = [1, 2, 3]
        for x in l:
          yield x
        x = await func()
        yield x

      def f1(x: AsyncIterator[Union[int, str]]):
        pass

      def f2(x: AsyncIterator[bool]):
        pass

      def f3(x: AsyncIterable[Union[int, str]]):
        pass

      def f4(x: AsyncIterable[bool]):
        pass

      def f5(x: AsyncGenerator[Union[int, str], Any]):
        pass

      def f6(x: AsyncGenerator[bool, Any]):
        pass

      f1(gen())
      f2(gen())  # wrong-arg-types[e1]
      f3(gen())
      f4(gen())  # wrong-arg-types[e2]
      f5(gen())
      f6(gen())  # wrong-arg-types[e3]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"bool.*Union\[int, str\]",
            "e2": r"bool.*Union\[int, str\]",
            "e3": r"bool.*Union\[int, str\]",
        },
    )

  def test_protocol(self):
    ty = self.Infer("""
      from typing import AsyncIterator, AsyncIterable, AsyncGenerator, AsyncContextManager, Any

      async def func():
        return "str"

      class AIterable:
        def __aiter__(self):
          return self

      class AIterator:
        def __aiter__(self):
          return self

        async def __anext__(self):
          if __random__:
            return 5
          raise StopAsyncIteration

      class ACtxMgr:
        async def __aenter__(self):
          return 5

        async def __aexit__(self, exc_type, exc_value, traceback):
          pass

      def f1(x: AsyncIterator):
        pass

      def f2(x: AsyncIterable):
        pass

      def f3(x: AsyncContextManager):
        pass

      async def f4():
        f1(AIterator())
        f2(AIterable())
        f3(ACtxMgr())
        async with ACtxMgr() as x:
          await func()
        return x
    """)
    self.assertTypesMatchPytd(
        ty,
        """
      from typing import Any, AsyncIterable, AsyncIterator, AsyncContextManager, Coroutine, TypeVar

      _TAIterable = TypeVar('_TAIterable', bound=AIterable)
      _TAIterator = TypeVar('_TAIterator', bound=AIterator)

      class ACtxMgr:
          def __aenter__(self) -> Coroutine[Any, Any, int]: ...
          def __aexit__(self, exc_type, exc_value, traceback) -> Coroutine[Any, Any, None]: ...

      class AIterable:
          def __aiter__(self: _TAIterable) -> _TAIterable: ...

      class AIterator:
          def __aiter__(self: _TAIterator) -> _TAIterator: ...
          def __anext__(self) -> Coroutine[Any, Any, int]: ...


      def f1(x: AsyncIterator) -> None: ...
      def f2(x: AsyncIterable) -> None: ...
      def f3(x: AsyncContextManager) -> None: ...
      def f4() -> Coroutine[Any, Any, int]: ...
      def func() -> Coroutine[Any, Any, str]: ...
    """,
    )

  def test_callable(self):
    self.Check("""
      from typing import Awaitable, Callable
      async def f1(a: str) -> str:
        return a
      async def f2(fun: Callable[[str], Awaitable[str]]) -> str:
        return await fun('a')
      async def f3() -> None:
        await f2(f1)
    """)

  def test_callable_with_imported_func(self):
    with self.DepTree([(
        "foo.py",
        """
      async def f1(a: str) -> str:
        return a
    """,
    )]):
      self.Check("""
        import foo
        from typing import Awaitable, Callable
        async def f2(fun: Callable[[str], Awaitable[str]]) -> str:
          return await fun('a')
        async def f3() -> None:
          await f2(foo.f1)
      """)

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_aiter(self):
    self.Check("""
      from typing import AsyncIterable, AsyncIterator
      async def gen1():
        yield 5

      async def gen2() -> AsyncIterable:
        yield 5

      async def gen3() -> AsyncIterable[int]:
        yield 5

      class gen4:
        async def __aiter__(self) -> AsyncIterator[int]:
          yield 5

      x1: AsyncIterator[int] = aiter(gen1())
      x2: AsyncIterator[int] = aiter(gen2())
      x3: AsyncIterator[int] = aiter(gen3())
      x4: AsyncIterator[int] = aiter(gen4())
    """)

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_aiter_error(self):
    errors = self.CheckWithErrors("""
      from typing import AsyncIterable, AsyncIterator, Iterable
      async def gen1():
        yield 5

      async def gen2() -> AsyncIterable:
        yield 5

      async def gen3() -> AsyncIterable[int]:
        yield 5

      class gen4:
        async def __aiter__(self) -> AsyncIterator[int]:
          yield 5

      x1: AsyncIterator[str] = aiter(gen1())  # annotation-type-mismatch[e1]
      x2: AsyncIterator[str] = aiter(gen2())  # this is ok because gen2() is effectively of type AsyncIterable[Any]
      x3: AsyncIterator[str] = aiter(gen3())  # annotation-type-mismatch[e3]
      x4: AsyncIterator[str] = aiter(gen4())  # annotation-type-mismatch[e4]

      aiter([5])  # wrong-arg-types[e5]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"str.*int",
            "e3": r"str.*int",
            "e4": r"str.*int",
            "e5": r"AsyncIterable.*list",
        },
    )

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_anext(self):
    self.Check("""
      from typing import AsyncIterator, Awaitable
      from typing_extensions import Self
      async def gen1():
        yield 5

      async def gen2() -> AsyncIterator:
        yield 5

      async def gen3() -> AsyncIterator[int]:
        yield 5

      class gen4:
        async def __anext__(self) -> int:
          return 5

        def __aiter__(self) -> Self:
          return self

      x1: Awaitable[int] = anext(gen1())
      x2: Awaitable[int] = anext(gen2())
      x3: Awaitable[int] = anext(gen3())
      x4: Awaitable[int] = anext(gen4())

      y1: Awaitable[int | str] = anext(gen1(), "done")
      y2: Awaitable[int | str] = anext(gen2(), "done")
      y3: Awaitable[int | str] = anext(gen3(), "done")
      y4: Awaitable[int | str] = anext(gen4(), "done")
    """)

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_anext_error(self):
    errors = self.CheckWithErrors("""
      from typing import AsyncIterator, Awaitable
      from typing_extensions import Self
      async def gen1():
        yield 5

      async def gen2() -> AsyncIterator:
        yield 5

      async def gen3() -> AsyncIterator[int]:
        yield 5

      class gen4:
        async def __anext__(self) -> int:
          return 5

        def __aiter__(self) -> Self:
          return self

      x1: Awaitable[str] = anext(gen1())  # annotation-type-mismatch[e1]
      x2: Awaitable[str] = anext(gen2())  # this is ok because gen2() is effectively of type AsyncIterator[Any]
      x3: Awaitable[str] = anext(gen3())  # annotation-type-mismatch[e3]
      x4: Awaitable[str] = anext(gen4())  # annotation-type-mismatch[e4]

      y1: Awaitable[str] = anext(gen1(), b"done")  # annotation-type-mismatch[e5]
      y2: Awaitable[str] = anext(gen2(), b"done")  # annotation-type-mismatch[e6]
      y3: Awaitable[str] = anext(gen3(), b"done")  # annotation-type-mismatch[e7]
      y4: Awaitable[str] = anext(gen4(), b"done")  # annotation-type-mismatch[e8]

      anext(iter([1]))  # wrong-arg-types[e9]
    """)
    self.assertErrorRegexes(
        errors,
        {
            "e1": r"Awaitable\[str\].*Awaitable\[int\]",
            "e3": r"Awaitable\[str\].*Awaitable\[int\]",
            "e4": r"Awaitable\[str\].*Awaitable\[int\]",
            "e5": r"Awaitable\[str\].*Awaitable\[Union\[bytes, int\]\]",
            "e6": r"Awaitable\[str\].*Awaitable",
            "e7": r"Awaitable\[str\].*Awaitable\[Union\[bytes, int\]\]",
            "e8": r"Awaitable\[str\].*Awaitable\[Union\[bytes, int\]\]",
            "e9": r"AsyncIterator.*listiterator\[int\]",
        },
    )

  @test_utils.skipBeforePy((3, 10), "New in 3.10")
  def test_async_gen_coroutines(self):
    self.Check("""
      from typing import Any, AsyncGenerator, Coroutine
      async def gen():
          yield 42

      x0: AsyncGenerator[int, None] = gen()
      x1: Coroutine[Any, Any, int] = gen().__anext__()
      x2: Coroutine[Any, Any, int] = gen().asend(None)
      x3: Coroutine[Any, Any, int] = gen().athrow(BaseException)
      x4: Coroutine[Any, Any, None] = gen().aclose()
    """)

  @test_utils.skipBeforePy((3, 11), "New in 3.11")
  def test_async_gen_coroutines_error(self):
    """Test whether the async for within async with does not fail at runtime."""
    self.Check("""
      def outer(f):
        async def wrapper(t, *args, **kwargs):
          if t is None:
            async with f():
              async for c in f():
                yield c
          else:
            async for c in f():
              yield c
        return wrapper
    """)

  @test_utils.skipBeforePy((3, 11), "New in 3.11")
  def test_async_for(self):
    self.Check("""
    async def iterate(num):
      try:
        async for s in range(num): # pytype: disable=attribute-error
          if s > 3:
            yield ''
      except ValueError as e:
        yield ''
      yield ''
    """)

  @test_utils.skipBeforePy((3, 11), "New in 3.11")
  def test_async_for_with_control_flow(self):
    self.Check("""
        from typing import Any
        import random
        async def iterate(stream: Any):
          async for _ in stream:
            if (random.randint(0, 100) != 30 or random.randint(0, 100) != 40):
              continue
            yield random.randint(0, 100)
    """)

  @test_utils.skipBeforePy((3, 11), "New in 3.11")
  def test_async_double_for_loop(self):
    self.Check("""
      def outer(f):
        async def wrapper(t, *args, **kwargs):
          if t is None:
            async with f():
              async for c in f():
                async for d in f():
                  yield c + d
                yield c
          else:
              async for c in f():
                async for d in f():
                  yield c + d
                yield c
        return wrapper
    """)


if __name__ == "__main__":
  test_base.main()
