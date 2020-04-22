"""Tests for async generators."""

from pytype.tests import test_base


class AsyncGeneratorFeatureTest(test_base.TargetPython3FeatureTest):
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
    self.assertTypesMatchPytd(ty, """
      from typing import Any, AsyncGenerator, Coroutine, Union

      x: AsyncGenerator[str, Any]
      y: AsyncGenerator[int, Any]

      def f(x) -> AsyncGenerator[Union[int, str], Any]: ...
      def func() -> Coroutine[Any, Any, str]: ...
      def gen() -> AsyncGenerator[Union[int, str], Any]: ...
    """)

  def test_annotation_error(self):
    errors = self.CheckWithErrors("""
      from typing import AsyncGenerator, AsyncIterator, AsyncIterable, Any, Union

      async def gen1() -> AsyncGenerator[bool, int]:
        yield 1  # bad-return-type[e1]

      async def gen2() -> AsyncIterator[bool]:
        yield 1  # bad-return-type[e2]

      async def gen3() -> AsyncIterable[bool]:
        yield 1  # bad-return-type[e3]

      async def gen4() -> int:  # invalid-annotation[e4]
        yield 1

      async def fun():
        g = gen1()
        await g.asend("str")  # wrong-arg-types[e5]
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"bool.*int", "e2": r"bool.*int", "e3": r"bool.*int",
        "e4": r"AsyncGenerator.*AsyncIterable.*AsyncIterator",
        "e5": r"int.*str"})

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
    self.assertErrorRegexes(errors, {
        "e1": r"bool.*Union\[int, str\]", "e2": r"bool.*Union\[int, str\]",
        "e3": r"bool.*Union\[int, str\]"})

  def test_protocol(self):
    ty = self.Infer("""
      from typing import AsyncIterator, AsyncIterable, AsyncGenerator, AsyncContextManager, Any

      async def func():
        return "str"

      class AIterable(object):
        def __aiter__(self):
          return self

      class AIterator(object):
        def __aiter__(self):
          return self

        async def __anext__(self):
          if __random__:
            return 5
          raise StopAsyncIteration

      class ACtxMgr(object):
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
    self.assertTypesMatchPytd(ty, """
      from typing import Any, AsyncIterable, AsyncIterator, AsyncContextManager, Coroutine, TypeVar

      _TAIterable = TypeVar('_TAIterable', bound=AIterable)
      _TAIterator = TypeVar('_TAIterator', bound=AIterator)

      class ACtxMgr(object):
          def __aenter__(self) -> Coroutine[Any, Any, int]: ...
          def __aexit__(self, exc_type, exc_value, traceback) -> Coroutine[Any, Any, None]: ...

      class AIterable(object):
          def __aiter__(self: _TAIterable) -> _TAIterable: ...

      class AIterator(object):
          def __aiter__(self: _TAIterator) -> _TAIterator: ...
          def __anext__(self) -> Coroutine[Any, Any, int]: ...


      def f1(x: AsyncIterator) -> None: ...
      def f2(x: AsyncIterable) -> None: ...
      def f3(x: AsyncContextManager) -> None: ...
      def f4() -> Coroutine[Any, Any, int]: ...
      def func() -> Coroutine[Any, Any, str]: ...
    """)

test_base.main(globals(), __name__ == "__main__")
