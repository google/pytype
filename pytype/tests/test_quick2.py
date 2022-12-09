"""Tests for --quick."""

from pytype.tests import test_base
from pytype.tests import test_utils


def make_quick(func):
  def wrapper(*args, **kwargs):
    kwargs["quick"] = True
    return func(*args, **kwargs)
  return wrapper


class QuickTest(test_base.BaseTest):
  """Tests for --quick."""

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    for method in ("Check", "CheckWithErrors", "Infer", "InferWithErrors"):
      setattr(cls, method, make_quick(getattr(cls, method)))

  def test_multiple_returns(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def add(x: int, y: int) -> int: ...
        def add(x: int,  y: float) -> float: ...
      """)
      self.Check("""
        import foo
        def f1():
          f2()
        def f2() -> int:
          return foo.add(42, f3())
        def f3():
          return 42
      """, pythonpath=[d.path])

  def test_multiple_returns_container(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Tuple
        def concat(x: int, y: int) -> Tuple[int, int]: ...
        def concat(x: int, y: float) -> Tuple[int, float]: ...
      """)
      self.Check("""
        from typing import Tuple
        import foo
        def f1():
          f2()
        def f2() -> Tuple[int, int]:
          return foo.concat(42, f3())
        def f3():
          return 42
      """, pythonpath=[d.path])

  def test_noreturn(self):
    self.Check("""
      from typing import NoReturn

      class A:
        pass

      class B:
        def _raise_notimplemented(self) -> NoReturn:
          raise NotImplementedError()
        def f(self, x):
          if __random__:
            outputs = 42
          else:
            self._raise_notimplemented()
          return outputs
        def g(self):
          outputs = self.f(A())
    """)

  def test_use_return_annotation(self):
    self.Check("""
      class Foo:
        def __init__(self):
          self.x = 3
      class Bar:
        def __init__(self):
          self.f()
        def f(self):
          assert_type(self.g().x, int)
        def g(self) -> Foo:
          return Foo()
    """)

  def test_use_return_annotation_with_typevar(self):
    self.Check("""
      from typing import List, TypeVar
      T = TypeVar('T')
      class Foo:
        def __init__(self):
          x = self.f()
          assert_type(x, list)
        def f(self):
          return self.g(0)
        def g(self, x: T) -> List[T]:
          return [x]
    """)

  def test_use_return_annotation_on_new(self):
    self.Check("""
      class Foo:
        def __new__(cls) -> "Foo":
          self = cls()
          self.x = __any_object__
          return self
        def __init__(self):
          self.y = 0
      def f():
        foo = Foo()
        assert_type(foo.x, "Any")
        assert_type(foo.y, "int")
    """)

  def test_async(self):
    self.Check("""
      async def f1() -> None:
        await f2()
      async def f2() -> None:
        await f3()
      async def f3() -> None:
        pass
    """)


if __name__ == "__main__":
  test_base.main()
