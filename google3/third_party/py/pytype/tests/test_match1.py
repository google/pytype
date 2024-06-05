"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype.tests import test_base
from pytype.tests import test_utils


class MatchTest(test_base.BaseTest):
  """Tests for matching types."""

  def test_type_against_callable(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable
        def f(x: Callable) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.f(int)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        def f() -> str: ...
      """)

  def test_match_static(self):
    ty = self.Infer("""
      s = {1}
      def f(x):
        # set.intersection is a static method:
        return s.intersection(x)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Set
      s = ...  # type: Set[int]

      def f(x) -> Set[int]: ...
    """)

  def test_generic_hierarchy(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Iterable
        def f(x: Iterable[str]) -> str: ...
      """)
      ty = self.Infer("""
        import a
        x = a.f(["a", "b", "c"])
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: str
      """)

  def test_generic(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import Generic, Iterable
        K = TypeVar("K")
        V = TypeVar("V")
        Q = TypeVar("Q")
        class A(Iterable[V], Generic[K, V]): ...
        class B(A[K, V]):
          def __init__(self):
            self = B[bool, str]
        def f(x: Iterable[Q]) -> Q: ...
      """)
      ty = self.Infer("""
        import a
        x = a.f(a.B())
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import a
        x = ...  # type: str
      """)

  def test_match_identity_function(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar
        T = TypeVar("T")
        def f(x: T) -> T: ...
      """)
      ty = self.Infer("""
        import foo
        v = foo.f(__any_object__)
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        import foo
        v = ...  # type: Any
      """)

  def test_callable_return(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, TypeVar
        T = TypeVar("T")
        def foo(func: Callable[[], T]) -> T: ...
      """)
      self.Check("""
        import foo
        class Foo:
          def __init__(self):
            self.x = 42
        foo.foo(Foo).x
      """, pythonpath=[d.path])

  def test_callable_union_return(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Callable, TypeVar, Union
        T1 = TypeVar("T1")
        T2 = TypeVar("T2")
        def foo(func: Callable[[], T1]) -> Union[T1, T2]: ...
      """)
      self.Check("""
        import foo
        class Foo:
          def __init__(self):
            self.x = 42
        v = foo.foo(Foo)
        if isinstance(v, Foo):
          v.x
      """, pythonpath=[d.path])

  def test_any_base_class(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Any
        class Foo(Any): pass
        class Bar: pass
        def f(x: Bar) -> None: ...
      """)
      self.Check("""
        import foo
        foo.f(foo.Foo())
      """, pythonpath=[d.path])

  def test_maybe_parameterized(self):
    self.Check("""
      import collections.abc
      class Foo(collections.abc.MutableMapping):
        pass
      def f(x: Foo):
        dict.__delitem__(x, __any_object__)  # pytype: disable=wrong-arg-types
    """)


if __name__ == "__main__":
  test_base.main()
