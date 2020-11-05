"""Tests for generators."""

from pytype.tests import test_base


class GeneratorTest(test_base.TargetIndependentTest):
  """Tests for iterators, generators, coroutines, and yield."""

  def test_next(self):
    ty = self.Infer("""
      def f():
        return next(i for i in [1,2,3])
    """)
    self.assertTypesMatchPytd(ty, """
      def f() -> int: ...
    """)

  def test_list(self):
    ty = self.Infer("""
      y = list(x for x in [1, 2, 3])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      y = ...  # type: List[int, ...]
    """)

  def test_reuse(self):
    ty = self.Infer("""
      y = list(x for x in [1, 2, 3])
      z = list(x for x in [1, 2, 3])
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      y = ...  # type: List[int, ...]
      z = ...  # type: List[int, ...]
    """)

  def test_next_with_default(self):
    ty = self.Infer("""
      def f():
        return next((i for i in [1,2,3]), None)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      def f() -> Union[int, NoneType]: ...
    """)

  def test_iter_match(self):
    ty = self.Infer("""
      class Foo(object):
        def bar(self):
          for x in __any_object__:
            return x
        def __iter__(self):
          return generator()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      class Foo(object):
        def bar(self) -> Any: ...
        def __iter__(self) -> Generator[nothing, nothing, nothing]: ...
    """)

  def test_coroutine_type(self):
    ty = self.Infer("""
      def foo(self):
        yield 3
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      def foo(self) -> Generator[int, Any, None]: ...
    """)

  def test_iteration_of_getitem(self):
    ty = self.Infer("""
      class Foo(object):
        def __getitem__(self, key):
          return "hello"

      def foo(self):
        for x in Foo():
          return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      class Foo(object):
        def __getitem__(self, key) -> str: ...
      def foo(self) -> Union[None, str]: ...
    """)

  def test_unpacking_of_getitem(self):
    ty = self.Infer("""
      class Foo(object):
        def __getitem__(self, pos):
          if pos < 3:
            return pos
          else:
            raise StopIteration
      x, y, z = Foo()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      _T0 = TypeVar("_T0")
      class Foo(object):
        def __getitem__(self, pos: _T0) -> _T0: ...
      x = ...  # type: int
      y = ...  # type: int
      z = ...  # type: int
    """)

  def test_none_check(self):
    ty = self.Infer("""
      def f():
        x = None if __random__ else 42
        if x:
          yield x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator
      def f() -> Generator[int, Any, None]: ...
    """)

  def test_yield_type(self):
    ty = self.Infer("""
      from typing import Generator
      def f(x):
        if x == 1:
          yield 1
        else:
          yield "1"

      x = f(2)
      y = f(1)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Generator, Union
      def f(x) -> Generator[Union[int, str], Any, None]: ...
      x = ...  # type: Generator[str, Any, None]
      y = ...  # type: Generator[int, Any, None]
    """)

test_base.main(globals(), __name__ == "__main__")
