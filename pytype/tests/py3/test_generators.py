"""Tests for generators."""

from pytype.tests import test_base


class GeneratorBasicTest(test_base.TargetPython3BasicTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def testReturnBeforeYield(self):
    self.Check("""
      from typing import Generator
      def f() -> generator:
        if __random__:
          return
        yield 5
    """)

  def testEmptyIterator(self):
    self.Check("""
      from typing import Iterator
      def f() -> Iterator:
        yield 5
    """)

  def testEmptyIterable(self):
    self.Check("""
      from typing import Iterable
      def f() -> Iterable:
        yield 5
    """)

  def testNoReturn(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generator
      def f() -> Generator[str, None, None]:
        yield 42
    """)
    self.assertErrorLogIs(errors, [(3, "bad-return-type", r"str.*int")])


class GeneratorFeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def testYieldRetType(self):
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
      def f(x) -> Generator[Union[int, str], Any, Union[int, str]]
      x = ...  # type: Generator[str, Any, str]
      y = ...  # type: Generator[int, Any, int]
    """)

  def testYieldTypeInfer(self):
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

  def testSendRetType(self):
    ty = self.Infer("""
      from typing import Generator, Any
      def f() -> Generator[str, int, Any]:
        x = yield "5"
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      def f() -> Generator[str, int, Any]
    """)

  def testParameterCount(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generator

      def func1() -> Generator[int, int, int]:
        x = yield 5
        return x

      def func2() -> Generator[int, int]:
        x = yield 5

      def func3() -> Generator[int]:
        yield 5
    """)
    self.assertErrorLogIs(errors, [
        (7, "invalid-annotation",
         r"typing.Generator\[_T, _T2, _V].*3.*2"),
        (10, "invalid-annotation",
         r"typing.Generator\[_T, _T2, _V].*3.*1")])


test_base.main(globals(), __name__ == "__main__")
