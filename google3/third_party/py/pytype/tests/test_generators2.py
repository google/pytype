"""Tests for generators."""

from pytype.tests import test_base
from pytype.tests import test_utils


class GeneratorBasicTest(test_base.BaseTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def test_return_before_yield(self):
    self.Check("""
      from typing import Generator
      def f() -> generator:
        if __random__:
          return
        yield 5
    """)

  def test_empty_iterator(self):
    self.Check("""
      from typing import Iterator
      def f() -> Iterator:
        yield 5
    """)

  def test_empty_iterable(self):
    self.Check("""
      from typing import Iterable
      def f() -> Iterable:
        yield 5
    """)

  def test_no_return(self):
    _, errors = self.InferWithErrors("""
      from typing import Generator
      def f() -> Generator[str, None, None]:
        yield 42  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})


class GeneratorFeatureTest(test_base.BaseTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def test_yield_ret_type(self):
    ty = self.Infer("""
      from typing import Generator
      def f(x):
        if x == 1:
          yield 1
          return 1
        else:
          yield "1"
          return "1"

      x = f(2)
      y = f(1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator, Union
      def f(x) -> Generator[Union[int, str], Any, Union[int, str]]: ...
      x = ...  # type: Generator[str, Any, str]
      y = ...  # type: Generator[int, Any, int]
    """)

  def test_yield_type_infer(self):
    ty = self.Infer("""
      def gen():
        l = [1, 2, 3]
        for x in l:
          yield x
        x = "str"
        yield x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator, Union

      def gen() -> Generator[Union[int, str], Any, None]: ...
    """)

  def test_send_ret_type(self):
    ty = self.Infer("""
      from typing import Generator, Any
      def f() -> Generator[str, int, Any]:
        x = yield "5"
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      def f() -> Generator[str, int, Any]: ...
    """)

  def test_parameter_count(self):
    _, errors = self.InferWithErrors("""
      from typing import Generator

      def func1() -> Generator[int, int, int]:
        x = yield 5
        return x

      def func2() -> Generator[int, int]:  # invalid-annotation[e1]
        x = yield 5

      def func3() -> Generator[int]:  # invalid-annotation[e2]
        yield 5
    """)
    self.assertErrorSequences(errors, {
        "e1": ["generator[int, int]", "generator[_T, _T2, _V]", "3", "2"],
        "e2": ["generator[int]", "generator[_T, _T2, _V]", "3", "1"]})

  def test_hidden_fields(self):
    self.Check("""
      from typing import Generator
      from types import GeneratorType
      a: generator = __any_object__
      a.gi_code
      a.gi_frame
      a.gi_running
      a.gi_yieldfrom

      b: Generator = __any_object__
      b.gi_code
      b.gi_frame
      b.gi_running
      b.gi_yieldfrom

      c: GeneratorType = __any_object__
      c.gi_code
      c.gi_frame
      c.gi_running
      c.gi_yieldfrom
    """)

  def test_empty_yield_from(self):
    # Regression test for https://github.com/google/pytype/issues/978.
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        from typing import Any, AsyncContextManager, Coroutine
        class Connection(AsyncContextManager): ...
        class ConnectionFactory(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def new(self) -> Coroutine[Any, Any, Connection]: ...
      """)
      self.Check("""
        from typing import Any
        from foo import ConnectionFactory
        class RetryingConnection:
          _connection_factory: ConnectionFactory
          _reinitializer: Any
          async def _run_loop(self):
            conn_fut = self._connection_factory.new()
            async with (await conn_fut) as connection:
              await connection
      """, pythonpath=[d.path])

  def test_yield_from(self):
    ty = self.Infer("""
      def foo():
        yield 'hello'
      def bar():
        yield from foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      def foo() -> Generator[str, Any, None]: ...
      def bar() -> Generator[str, Any, None]: ...
    """)

  def test_yield_from_check_return(self):
    self.CheckWithErrors("""
      from typing import Generator
      def foo():
        yield 'hello'
      def bar() -> Generator[str, None, None]:
        yield from foo()
      def baz() -> Generator[int, None, None]:
        yield from foo()  # bad-return-type
    """)


if __name__ == "__main__":
  test_base.main()
