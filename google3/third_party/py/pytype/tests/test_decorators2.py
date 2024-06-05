"""Test decorators."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class AnnotatedDecoratorsTest(test_base.BaseTest):
  """A collection of tested examples of annotated decorators."""

  def test_identity_decorator(self):
    ty = self.Infer("""
      from typing import Any, Callable, TypeVar
      Fn = TypeVar('Fn', bound=Callable[..., Any])

      def decorate(fn: Fn) -> Fn:
        return fn

      @decorate
      def f(x: int) -> str:
        return str(x)

      @decorate
      class Foo:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, TypeVar
      Fn = TypeVar('Fn', bound=Callable)
      def decorate(fn: Fn) -> Fn: ...
      def f(x: int) -> str: ...
      class Foo: ...
    """)
    # Prints the inferred types as a stub file and tests that the decorator
    # works correctly when imported in another file.
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      ty = self.Infer("""
        import foo

        @foo.decorate
        def f(x: str) -> int:
          return int(x)

        @foo.decorate
        class Bar:
          pass
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import foo
      def f(x: str) -> int: ...
      class Bar: ...
    """)

  def test_decorator_factory(self):
    ty = self.Infer("""
      from typing import Any, Callable, TypeVar
      Fn = TypeVar('Fn', bound=Callable[..., Any])

      def decorate(**options: Any) -> Callable[[Fn], Fn]:
        def inner(fn):
          return fn
        return inner

      @decorate()
      def f(x: int) -> str:
        return str(x)

      @decorate(x=0, y=False)
      def g() -> float:
        return 0.0

      @decorate()
      class Foo:
        pass

      @decorate(x=0, y=False)
      class Bar:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, TypeVar
      Fn = TypeVar('Fn', bound=Callable)
      def decorate(**options) -> Callable[[Fn], Fn]: ...
      def f(x: int) -> str: ...
      def g() -> float: ...
      class Foo: ...
      class Bar: ...
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      ty = self.Infer("""
        import foo

        @foo.decorate()
        def f() -> None:
          return None

        @foo.decorate(z=42)
        def g(x: int, y: int) -> int:
          return x + y

        @foo.decorate()
        class Foo:
          pass

        @foo.decorate(z=42)
        class Bar:
          pass
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import foo
      def f() -> None: ...
      def g(x: int, y: int) -> int: ...
      class Foo: ...
      class Bar: ...
    """)

  def test_identity_or_factory(self):
    ty = self.Infer("""
      from typing import Any, Callable, overload, TypeVar
      Fn = TypeVar('Fn', bound=Callable[..., Any])

      @overload
      def decorate(fn: Fn) -> Fn: ...

      @overload
      def decorate(fn: None = None, **options: Any) -> Callable[[Fn], Fn]: ...

      def decorate(fn=None, **options):
        if fn:
          return fn
        def inner(fn):
          return fn
        return inner

      @decorate
      def f() -> bool:
        return True

      @decorate()
      def g(x: complex) -> float:
        return x.real

      @decorate
      class Foo:
        pass

      @decorate(x=3.14)
      class Bar:
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, overload, TypeVar
      Fn = TypeVar('Fn', bound=Callable)

      @overload
      def decorate(fn: Fn) -> Fn: ...
      @overload
      def decorate(fn: None = ..., **options) -> Callable[[Fn], Fn]: ...

      def f() -> bool: ...
      def g(x: complex) -> float: ...
      class Foo: ...
      class Bar: ...
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      ty = self.Infer("""
        import foo

        @foo.decorate
        def f(x: float) -> str:
          return str(x)

        @foo.decorate(y=False, z=None)
        def g(x: int, y: float) -> float:
          return x + y

        @foo.decorate
        class Foo:
          pass

        @foo.decorate()
        class Bar:
          pass
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      import foo
      def f(x: float) -> str: ...
      def g(x: int, y: float) -> float: ...
      class Foo: ...
      class Bar: ...
    """)


class DecoratorsTest(test_base.BaseTest):
  """Test decorators."""

  def test_annotated_super_call_under_bad_decorator(self):
    self.InferWithErrors("""
      class Foo:
        def Run(self) -> None: ...
      class Bar(Foo):
        @bad_decorator  # name-error
        def Run(self):
          return super(Bar, self).Run()
    """)

  def test_replace_self_to_stararg(self):
    # Without decorator, `self` will be in `signature.param_names`.
    # But after replacing, `*args` won't be in `signature.param_names`.
    self.Check("""
      from typing import TypeVar

      T = TypeVar('T')
      def dec(func):
        def f(*args: T, **kwargs: T):
          pass

        return f

      class MyClass:
        @dec
        def func(self, x):
          pass

      x = MyClass()
      x.func(12)
    """)

  def test_instance_as_decorator_error(self):
    errors = self.CheckWithErrors("""
      class Decorate:
        def __call__(self, func):
          return func
      class Foo:
        @classmethod  # not-callable>=3.11
        @Decorate  # forgot to instantiate Decorate  # wrong-arg-count[e]>=3.11
        def bar(cls):  # wrong-arg-count[e]<3.11  # not-callable<3.11
          pass
      Foo.bar()
    """)
    self.assertErrorRegexes(errors, {"e": r"Decorate.*1.*2"})

  def test_uncallable_instance_as_decorator(self):
    errors = self.CheckWithErrors("""
      class Decorate:
        pass  # forgot to define __call__
      class Foo:
        @classmethod  # not-callable>=3.11
        @Decorate  # forgot to instantiate Decorate  # wrong-arg-count[e1]>=3.11
        def bar(cls):  # wrong-arg-count[e1]<3.11  # not-callable<3.11
          pass
      Foo.bar()
    """)
    self.assertErrorRegexes(errors, {"e1": r"Decorate.*1.*2"})

  def test_instance_method_with_annotated_decorator(self):
    ty = self.Infer("""
      from typing import Any, Callable
      def decorate(f: Callable[[Any, int], int]) -> Callable[[Any, int], int]:
        return f
      class Foo:
        @decorate
        def f(self, x):
          return x
      Foo().f(0)
      Foo.f(Foo(), 0)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, Callable
      def decorate(f: Callable[[Any, int], int]) -> Callable[[Any, int], int]:
        ...
      class Foo:
        def f(self, _1: int) -> int: ...
    """)

  def test_instance_method_with_unannotated_decorator(self):
    with self.DepTree([("lock.py", """
      class Lock:
        def __call__(self, f):
          def wrapped(a, b):
            pass
          return wrapped
    """)]):
      ty = self.Infer("""
        import lock
        class Foo:
          @lock.Lock()
          def f(self):
            pass
        Foo().f(0)
      """)
      self.assertTypesMatchPytd(ty, """
        import lock
        from typing import Any
        class Foo:
          def f(self, _1) -> Any: ...
      """)

  def test_instance_method_from_generic_callable(self):
    ty = self.Infer("""
      from typing import Callable, TypeVar
      T = TypeVar('T')
      def decorate(f) -> Callable[[T], T]:
        return lambda x: x
      class Foo:
        @decorate
        def f(self):
          pass
      assert_type(Foo().f(), Foo)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Callable, TypeVar
      T = TypeVar('T')
      def decorate(f) -> Callable[[T], T]: ...
      class Foo:
        def f(self: T) -> T: ...
    """)

  def test_typevar_in_decorated_function_in_function(self):
    self.Check("""
      from typing import Any, TypeVar
      T = TypeVar('T')
      def decorate(f) -> Any:
        return f
      def f_out(x: T) -> T:
        @decorate
        def f_in() -> T:
          return x
        return x
    """)

  def test_typevar_in_decorated_method_in_class(self):
    self.Check("""
      from typing import Any, Generic, TypeVar
      T = TypeVar('T')
      def decorate(f) -> Any:
        return f
      class C(Generic[T]):
        @decorate
        def f(self, x: T):
          pass
    """)

  def test_self_in_decorated_method(self):
    self.Check("""
      from typing import Any
      def decorate(f) -> Any:
        return f
      class C:
        @decorate
        def f(self):
          assert_type(self, C)
    """)

  def test_self_in_contextmanager(self):
    self.CheckWithErrors("""
      import contextlib
      class Foo:
        @contextlib.contextmanager
        def ctx(self):
          print(self.attribute_error)  # attribute-error
    """)


if __name__ == "__main__":
  test_base.main()
