"""Test decorators."""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class AnnotatedDecoratorsTest(test_base.TargetPython3BasicTest):
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
    with file_utils.Tempdir() as d:
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
      foo: module
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
    with file_utils.Tempdir() as d:
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
      foo: module
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
    with file_utils.Tempdir() as d:
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
      foo: module
      def f(x: float) -> str: ...
      def g(x: int, y: float) -> float: ...
      class Foo: ...
      class Bar: ...
    """)


class DecoratorsTest(test_base.TargetPython3BasicTest):
  """Test decorators."""

  def test_annotated_super_call_under_bad_decorator(self):
    self.InferWithErrors("""
      class Foo(object):
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

      class MyClass(object):
        @dec
        def func(self, x):
          pass

      x = MyClass()
      x.func(12)
    """)

  @test_utils.skipFromPy((3, 8), "error line number changed in 3.8")
  def test_instance_as_decorator_error_pre_38(self):
    errors = self.CheckWithErrors("""
      class Decorate(object):
        def __call__(self, func):
          return func
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate  # wrong-arg-count[e]
        def bar(cls):
          pass
      Foo.bar()
    """)
    self.assertErrorRegexes(errors, {"e": r"Decorate.*1.*2"})

  @test_utils.skipBeforePy((3, 8), "error line number changed in 3.8")
  def test_instance_as_decorator_error(self):
    errors = self.CheckWithErrors("""
      class Decorate(object):
        def __call__(self, func):
          return func
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate
        def bar(cls):  # wrong-arg-count[e]
          pass
      Foo.bar()
    """)
    self.assertErrorRegexes(errors, {"e": r"Decorate.*1.*2"})

  @test_utils.skipFromPy((3, 8), "error line number changed in 3.8")
  def test_uncallable_instance_as_decorator_pre_38(self):
    errors = self.CheckWithErrors("""
      class Decorate(object):
        pass  # forgot to define __call__
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate  # wrong-arg-count[e1]
        def bar(cls):
          pass
      Foo.bar()  # not-callable[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Decorate.*1.*2", "e2": r"Decorate"})

  @test_utils.skipBeforePy((3, 8), "error line number changed in 3.8")
  def test_uncallable_instance_as_decorator(self):
    errors = self.CheckWithErrors("""
      class Decorate(object):
        pass  # forgot to define __call__
      class Foo(object):
        @classmethod
        @Decorate  # forgot to instantiate Decorate
        def bar(cls):  # wrong-arg-count[e1]
          pass
      Foo.bar()  # not-callable[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Decorate.*1.*2", "e2": r"Decorate"})


test_base.main(globals(), __name__ == "__main__")
