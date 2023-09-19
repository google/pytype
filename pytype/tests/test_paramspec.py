"""PEP 612 tests."""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy((3, 10), "ParamSpec is new in 3.10")
class ParamSpecTest(test_base.BaseTest):
  """Tests for ParamSpec."""

  def test_basic(self):
    ty = self.Infer("""
      from typing import ParamSpec
      P = ParamSpec("P")
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import ParamSpec
      P = ParamSpec("P")
    """)

  def test_import(self):
    with test_utils.Tempdir() as d:
      d.create_file("a.pyi", """P = ParamSpec("P")""")
      ty = self.Infer("""
        from a import P
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import ParamSpec
        P = ParamSpec("P")
      """)

  def test_invalid(self):
    ty, errors = self.InferWithErrors("""
      from typing import ParamSpec
      T = ParamSpec()  # invalid-typevar[e1]
      T = ParamSpec("T")  # ok
      T = ParamSpec(42)  # invalid-typevar[e2]
      T = ParamSpec(str())  # invalid-typevar[e3]
      T = ParamSpec("T", str, int if __random__ else float)  # invalid-typevar[e4]
      T = ParamSpec("T", 0, float)  # invalid-typevar[e5]
      T = ParamSpec("T", str)  # invalid-typevar[e6]
      # pytype: disable=not-supported-yet
      S = ParamSpec("S", covariant=False)  # ok
      T = ParamSpec("T", covariant=False)  # duplicate ok
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import ParamSpec
      S = ParamSpec("S")
      T = ParamSpec("T")
    """)
    self.assertErrorRegexes(errors, {
        "e1": r"wrong arguments", "e2": r"Expected.*str.*Actual.*int",
        "e3": r"constant str", "e4": r"constraint.*Must be constant",
        "e5": r"Expected.*_1:.*type.*Actual.*_1: int", "e6": r"0 or more than 1"
    })

  def test_print_args(self):
    ty = self.Infer("""
      from typing import ParamSpec
      S = ParamSpec("S", bound=float, covariant=True)
    """, deep=False)
    # The "covariant" keyword is ignored for now.
    self.assertTypesMatchPytd(ty, """
      from typing import ParamSpec
      S = ParamSpec("S", bound=float)
    """)

  def test_paramspec_in_def(self):
    ty = self.Infer("""
      from typing import Callable, ParamSpec
      P = ParamSpec("P")

      def f(x: Callable[P, int]) -> Callable[P, int]:
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, ParamSpec
      P = ParamSpec("P")

      def f(x: Callable[P, int]) -> Callable[P, int]: ...
    """)

  def test_concatenate_in_def(self):
    ty = self.Infer("""
      from typing import Callable, Concatenate, ParamSpec
      P = ParamSpec("P")

      def f(x: Callable[Concatenate[int, P], int]) -> Callable[P, int]:
        return x
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, Concatenate, ParamSpec
      P = ParamSpec("P")

      def f(x: Callable[Concatenate[int, P], int]) -> Callable[P, int]: ...
    """)

  def test_drop_param(self):
    self.Check("""
      from typing import Callable, Concatenate, ParamSpec

      P = ParamSpec("P")

      def f(x: Callable[Concatenate[int, P], int], y: int) -> Callable[P, int]:
        return lambda k: x(y, k)

      def g(x: int, y: str) -> int:
        return 42

      a = f(g, 1)
      assert_type(a, Callable[[str], int])
    """)

  def test_add_param(self):
    self.Check("""
      from typing import Callable, Concatenate, ParamSpec

      P = ParamSpec("P")

      def f(x: Callable[P, int]) -> Callable[Concatenate[int, P], int]:
        return lambda p, q: x(q)

      def g(x: str) -> int:
        return 42

      a = f(g)
      assert_type(a, Callable[[int, str], int])
    """)

  def test_change_return_type(self):
    self.Check("""
      from typing import Callable, Concatenate, ParamSpec

      P = ParamSpec("P")

      def f(x: Callable[P, int]) -> Callable[P, str]:
        return lambda p: str(x(p))

      def g(x: int) -> int:
        return 42

      a = f(g)
      assert_type(a, Callable[[int], str])
    """)

  def test_typevar(self):
    self.Check("""
      from typing import Callable, Concatenate, List, ParamSpec, TypeVar

      P = ParamSpec("P")
      T = TypeVar('T')

      def f(x: Callable[P, T]) -> Callable[P, List[T]]:
        def inner(p):
          return [x(p)]
        return inner

      def g(x: int) -> int:
        return 42

      def h(x: bool) -> str:
        return '42'

      a = f(g)
      assert_type(a, Callable[[int], List[int]])
      b = f(h)
      assert_type(b, Callable[[bool], List[str]])
    """)

  def test_args_and_kwargs(self):
    self.Check("""
      from typing import ParamSpec, Callable, TypeVar

      P = ParamSpec("P")
      T = TypeVar("T")

      def decorator(f: Callable[P, T]) -> Callable[P, T]:
        def foo(*args: P.args, **kwargs: P.kwargs) -> T:
          return f(*args, **kwargs)
        return foo

      def g(x: int, y: str) -> bool:
        return False

      a = decorator(g)
      b = a(1, '2')
      assert_type(b, bool)
    """)


_DECORATOR_PYI = """
  from typing import TypeVar, ParamSpec, Callable, List

  T = TypeVar("T")
  P = ParamSpec("P")

  def decorator(fn: Callable[P, T]) -> Callable[P, List[T]]: ...
"""


@test_utils.skipBeforePy((3, 10), "ParamSpec is new in 3.10")
class PyiParamSpecTest(test_base.BaseTest):
  """Tests for ParamSpec imported from pyi files."""

  def test_decorator(self):
    with self.DepTree([("foo.pyi", _DECORATOR_PYI)]):
      ty, _ = self.InferWithErrors("""
        import foo

        class A:
          pass

        @foo.decorator
        def h(a: A, b: str) -> int:
          return 10

        p = h(A(), b='2')
        q = h(1, 2)  # wrong-arg-types
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, Any

      p: List[int]
      q: Any

      class A: ...

      def h(a: A, b: str) -> List[int]: ...
   """)

  def test_method_decoration(self):
    with self.DepTree([("foo.pyi", _DECORATOR_PYI)]):
      ty, _ = self.InferWithErrors("""
        import foo

        class A:
          pass

        class B:
          @foo.decorator
          def h(a: A, b: str) -> int:
            return 10
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, Any

      class A: ...

      class B:
        def h(a: A, b: str) -> List[int]: ...
   """)

  def test_multiple_decorators(self):
    """Check that we don't cache the decorator type params."""
    with self.DepTree([("foo.pyi", _DECORATOR_PYI)]):
      self.Check("""
        import foo

        @foo.decorator
        def f(x) -> str:
          return "a"

        @foo.decorator
        def g() -> int:
          return 42

        def h() -> list[str]:
          return f(10)

        def k() -> list[int]:
          return g()
      """)

  def test_imported_paramspec(self):
    with self.DepTree([("foo.pyi", _DECORATOR_PYI)]):
      ty, _ = self.InferWithErrors("""
        from foo import decorator

        class A:
          pass

        @decorator
        def h(a: A, b: str) -> int:
          return 10

        p = h(A(), b='2')
        q = h(1, 2)  # wrong-arg-types
      """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, List, ParamSpec, TypeVar, Any

      p: List[int]
      q: Any

      P = ParamSpec('P')
      T = TypeVar('T')

      class A: ...

      def decorator(fn: Callable[P, T]) -> Callable[P, List[T]]: ...
      def h(a: A, b: str) -> List[int]: ...
   """)

  def test_concatenate(self):
    # TODO(b/217789659):
    # - Should change_arg preserve the name of the posarg?
    # - Should paramspecs in error messages be changed to ...?
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar, ParamSpec, Concatenate, Callable

      T = TypeVar("T")
      P = ParamSpec("P")

      def change_arg(fn: Callable[Concatenate[int, P], T]) -> Callable[Concatenate[str, P], T]: ...
      def drop_arg(fn: Callable[Concatenate[int, P], T]) -> Callable[P, T]: ...
      def add_arg(fn: Callable[P, T]) -> Callable[Concatenate[int, P], T]: ...
      def mismatched(fn: Callable[Concatenate[str, P], T]) -> Callable[Concatenate[str, P], T]: ...
    """)]):
      ty, err = self.InferWithErrors("""
        import foo

        @foo.change_arg
        def f(a: int, b: str) -> int:
          return 10

        @foo.drop_arg
        def g(a: int, b: str) -> int:
          return 10

        @foo.add_arg
        def h(a: int, b: str) -> int:
          return 10

        @foo.mismatched
        def k(a: int, b: str) -> int:  # wrong-arg-types[e]
          return 10
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import Any

      k: Any

      def f(_0: str, b: str) -> int: ...
      def g(b: str) -> int: ...
      def h(_0: int, /, a: int, b: str) -> int: ...
   """)
    self.assertErrorSequences(err, {
        "e": ["Expected", "fn: Callable[Concatenate[str, P], Any]",
              "Actual", "fn: Callable[[int, str], int]"]})

  def test_overloaded_argument(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar, ParamSpec, Callable, List

      T = TypeVar("T")
      P = ParamSpec("P")

      def decorator(fn: Callable[P, T]) -> Callable[P, List[T]]: ...

      @overload
      def f(x: str) -> int: ...
      @overload
      def f(x: str, *, y: int = 0) -> int: ...
    """)]):
      ty, _ = self.InferWithErrors("""
        import foo

        f = foo.decorator(foo.f)
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, overload

      @overload
      def f(x: str) -> List[int]: ...
      @overload
      def f(x: str, *, y: int = ...) -> List[int]: ...
   """)

  def test_starargs(self):
    with self.DepTree([("foo.pyi", _DECORATOR_PYI)]):
      ty = self.Infer("""
        import foo

        class A:
          pass

        class B:
          @foo.decorator
          def h(a: A, b: str, *args, **kwargs) -> int:
            return 10

        @foo.decorator
        def s(*args) -> int:
          return 10

        @foo.decorator
        def k(**kwargs) -> int:
          return 10
      """)
    self.assertTypesMatchPytd(ty, """
      import foo
      from typing import List, Any

      class A: ...

      class B:
        def h(a: A, b: str, *args, **kwargs) -> List[int]: ...

      def s(*args) -> List[int]: ...
      def k(**kwargs) -> List[int]: ...
   """)

  def test_callable(self):
    with self.DepTree([("foo.pyi", """
      from typing import TypeVar, ParamSpec, Concatenate, Callable

      T = TypeVar("T")
      P = ParamSpec("P")

      def add_arg(fn: Callable[P, T]) -> Callable[Concatenate[int, P], T]: ...
    """)]):
      self.Check("""
        import foo
        from typing import Callable, List

        def f(method: Callable[[int, str], bool]):
          a = foo.add_arg(method)
          b = a(1, 2, '3')
          assert_type(b, bool)
      """)

  def test_match_callable(self):
    with self.DepTree([("foo.pyi", """
      from typing import Any, Callable, ParamSpec
      P = ParamSpec('P')
      def f(x: Callable[P, Any]) -> Callable[P, Any]: ...
    """)]):
      self.Check("""
        import foo

        # Any function should match `Callable[P, Any]`.
        def f0():
          pass
        def f1(x):
          pass
        def f2(x1, x2):
          pass
        foo.f(f0)
        foo.f(f1)
        foo.f(f2)

        class C0:
          def __call__(self):
            pass
        class C1:
          def __call__(self, x1):
            pass
        class C2:
          def __call__(self, x1, x2):
            pass

        # Any class object should match.
        foo.f(C0)

        # Any class instance with a `__call__` method should match.
        foo.f(C0())
        foo.f(C1())
        foo.f(C2())
      """)

  def test_callable_class_inference(self):
    with self.DepTree([("foo.pyi", """
      from typing import Any, Callable, ParamSpec
      P = ParamSpec('P')
      def f(x: Callable[P, Any]) -> Callable[P, Any]: ...
    """)]):
      ty = self.Infer("""
        import foo
        class C:
          def __call__(self, x: int, y) -> str:
            return str(x)
        f = foo.f(C())
      """)
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Any
        class C:
          def __call__(self, x: int, y) -> str: ...
        def f(x: int, y) -> Any: ...
      """)


class ContextlibTest(test_base.BaseTest):
  """Test some more complex uses of contextlib."""

  def test_wrapper(self):
    self.Check("""
      import contextlib
      import functools

      from typing import Callable, ContextManager, Iterator, TypeVar

      T = TypeVar("T")

      class Builder:
        def __init__(self, exit_stack: contextlib.ExitStack):
          self._stack = exit_stack

        def _enter_context(self, manager: ContextManager[T]) -> T:
          return self._stack.enter_context(manager)

      def context_manager(func: Callable[..., Iterator[T]]) -> Callable[..., T]:
        cm_func = contextlib.contextmanager(func)

        @functools.wraps(cm_func)
        def _context_manager_wrap(self: Builder, *args, **kwargs):
          return self._enter_context(cm_func(self, *args, **kwargs))

        return _context_manager_wrap
      """)


if __name__ == "__main__":
  test_base.main()
