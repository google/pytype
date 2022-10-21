"""Tests for typing.overload."""

from pytype.pytd import pytd_utils
from pytype.tests import test_base
from pytype.tests import test_utils


class OverloadTest(test_base.BaseTest):
  """Tests for typing.overload."""

  def test_simple(self):
    self.Check("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      def f(x):
        return x
    """)

  def test_bad_implementation(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      @overload
      def f(x: int) -> str:
        pass
      def f(x):
        return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"str.*int"})

  def test_bad_call(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      def f(x):
        return x
      f("")  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_sub_return(self):
    ty = self.Infer("""
      from typing import overload
      @overload
      def f(x: int) -> float:
        pass
      def f(x):
        return x
      v = f(0)
    """)
    self.assertTypesMatchPytd(ty, """
      def f(x: int) -> float: ...
      v: float
    """)

  def test_multiple_overload(self):
    self.Check("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f() -> None:
        pass
      def f(x=None):
        return x
      f(0)
      f()
    """)

  def test_multiple_overload_bad_implementation(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: str) -> int:
        pass
      def f(x):
        return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_multiple_overload_bad_call(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: int, y: str) -> str:
        pass
      def f(x, y=None):
        return x if y is None else y
      f("")  # wrong-arg-types[e1]
      f(0, 0)  # wrong-arg-types[e2]
    """)
    self.assertErrorRegexes(errors, {"e1": r"int.*str", "e2": r"str.*int"})

  def test_pyi(self):
    src = """
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      @overload
      def f(x: str) -> str:
        pass
      def f(x):
        return x
      def g():
        return f
    """
    ty = self.Infer(src, analyze_annotated=False)
    self.assertTrue(
        pytd_utils.ASTeq(ty, self.Infer(src, analyze_annotated=True)))
    self.assertTypesMatchPytd(ty, """
      from typing import Callable
      @overload
      def f(x: int) -> int: ...
      @overload
      def f(x: str) -> str: ...
      def g() -> Callable: ...
    """)
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(ty))
      errors = self.CheckWithErrors("""
        import foo
        foo.f(0)  # ok
        foo.f("")  # ok
        foo.f(0.0)  # wrong-arg-types[e]
      """, pythonpath=[d.path])
    self.assertErrorRegexes(errors, {"e": r"int.*float"})

  def test_method_bad_implementation(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      class Foo:
        @overload
        def f(self, x: int) -> int:
          pass
        @overload
        def f(self, x: str) -> int:
          pass
        def f(self, x):
          return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*str"})

  def test_method_pyi(self):
    src = """
      from typing import overload
      class Foo:
        @overload
        def f(self, x: int) -> int:
          pass
        @overload
        def f(self, x: str) -> str:
          pass
        def f(self, x):
          return x
    """
    ty = self.Infer(src, analyze_annotated=False)
    self.assertTrue(
        pytd_utils.ASTeq(ty, self.Infer(src, analyze_annotated=True)))
    self.assertTypesMatchPytd(ty, """
      class Foo:
        @overload
        def f(self, x: int) -> int: ...
        @overload
        def f(self, x: str) -> str: ...
    """)

  def test_call_overload(self):
    errors = self.CheckWithErrors("""
      from typing import overload
      @overload
      def f(x: int) -> int:
        pass
      f(0)  # not-callable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"overload"})

  def test_varargs(self):
    ty = self.Infer("""
      from typing import overload
      @overload
      def f() -> int: ...
      @overload
      def f(x: float, *args) -> float: ...
      def f(*args):
        return args[0] if args else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f() -> int: ...
      @overload
      def f(x: float, *args) -> float: ...
    """)

  def test_varargs_and_kwargs(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import overload
        @overload
        def f(x: int) -> int: ...
        @overload
        def f(x: str) -> str: ...
      """)
      ty = self.Infer("""
        import foo
        def f1(*args):
          return foo.f(*args)
        def f2(**kwargs):
          return foo.f(**kwargs)
        def f3():
          return foo.f(*(0,))
        def f4():
          return foo.f(**{"x": "y"})
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Any
        def f1(*args) -> Any: ...
        def f2(**kwargs) -> Any: ...
        def f3() -> int: ...
        def f4() -> str: ...
      """)

  def test_init_kwargs_overloads(self):
    ty = self.Infer("""
      from typing import overload
      class Foo:
        @overload
        def __init__(self, x: int, **kw) -> None: ...
        @overload
        def __init__(self, **kw) -> None: ...
        def __init__(self, x: int, **kw): pass
    """)
    self.assertTypesMatchPytd(ty, """
        from typing import overload
        class Foo:
          @overload
          def __init__(self, x: int, **kw) -> None: ...
          @overload
          def __init__(self, **kw) -> None: ...
      """)

  def test_use_init_kwargs_overloads(self):
    with self.DepTree([("foo.py", """
      from typing import overload
      class Foo:
        @overload
        def __init__(self, x: int, **kw) -> None: ...
        @overload
        def __init__(self, **kw) -> None: ...
        def __init__(self, x: int, **kw): pass
    """)]):
      self.Check("""
        import foo
        foo.Foo(0)
      """)

  def test_generic_class(self):
    self.Check("""
      from typing import Generic, List, TypeVar, overload
      T = TypeVar('T')
      class Foo(Generic[T]):
        @overload
        def f(self, x: int) -> T: ...
        @overload
        def f(self, x: str) -> List[T]: ...
        def f(self, x):
          return __any_object__
    """)

  def test_multiple_matches_pyi(self):
    with self.DepTree([("foo.pyi", """
      from typing import overload
      @overload
      def f(x: str) -> str: ...
      @overload
      def f(x: bytes) -> bytes: ...
    """)]):
      self.Check("""
        import foo
        from typing import Tuple
        def f(arg) -> Tuple[str, str]:
          x = 'hello world' if __random__ else arg
          y = arg if __random__ else 'goodbye world'
          return foo.f(x), foo.f(y)
      """)


class OverloadTestPy3(test_base.BaseTest):
  """Python 3 tests for typing.overload."""

  def test_kwargs(self):
    ty = self.Infer("""
      from typing import overload
      @overload
      def f() -> int: ...
      @overload
      def f(*, x: float = 0.0, **kwargs) -> float: ...
      def f(**kwargs):
        return kwargs['x'] if kwargs else 0
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import overload
      @overload
      def f() -> int: ...
      @overload
      def f(*, x: float = ..., **kwargs) -> float: ...
    """)


if __name__ == "__main__":
  test_base.main()
