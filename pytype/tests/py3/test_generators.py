"""Tests for generators."""

from pytype.tests import test_base


class GeneratorBasicTest(test_base.TargetPython3BasicTest):
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


class GeneratorFeatureTest(test_base.TargetPython3FeatureTest):
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
    self.assertErrorRegexes(errors, {
        "e1": r"typing.Generator\[_T, _T2, _V].*3.*2",
        "e2": r"typing.Generator\[_T, _T2, _V].*3.*1"})


test_base.main(globals(), __name__ == "__main__")
