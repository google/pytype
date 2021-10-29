"""Tests for reloading generated pyi."""

from pytype.tests import test_base


class ReingestTest(test_base.BaseTest):
  """Tests for reloading the pyi we generate."""

  def test_type_parameter_bound(self):
    foo = """
      from typing import TypeVar
      T = TypeVar("T", bound=float)
      def f(x: T) -> T: return x
    """
    with self.DepTree([("foo.py", foo, dict(deep=False))]):
      _, errors = self.InferWithErrors("""
        import foo
        foo.f("")  # wrong-arg-types[e]
      """)
      self.assertErrorRegexes(errors, {"e": r"float.*str"})

  def test_default_argument_type(self):
    foo = """
      from typing import Any, Callable, TypeVar
      T = TypeVar("T")
      def f(x):
        return True
      def g(x: Callable[[T], Any]) -> T: ...
    """
    with self.DepTree([("foo.py", foo)]):
      self.Check("""
        import foo
        foo.g(foo.f).upper()
      """)

  def test_duplicate_anystr_import(self):
    dep1 = """
      from typing import AnyStr
      def f(x: AnyStr) -> AnyStr:
        return x
    """
    dep2 = """
      from typing import AnyStr
      from dep1 import f
      def g(x: AnyStr) -> AnyStr:
        return x
    """
    deps = [("dep1.py", dep1), ("dep2.py", dep2)]
    with self.DepTree(deps):
      self.Check("import dep2")


class ReingestTestPy3(test_base.BaseTest):
  """Python 3 tests for reloading the pyi we generate."""

  def test_instantiate_pyi_class(self):
    foo = """
      import abc
      class Foo(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def foo(self):
          pass
      class Bar(Foo):
        def foo(self):
          pass
    """
    with self.DepTree([("foo.py", foo)]):
      _, errors = self.InferWithErrors("""
        import foo
        foo.Foo()  # not-instantiable[e]
        foo.Bar()
      """)
      self.assertErrorRegexes(errors, {"e": r"foo\.Foo.*foo"})

  def test_use_class_attribute_from_annotated_new(self):
    foo = """
      class Foo:
        def __new__(cls) -> "Foo":
          return cls()
      class Bar:
        FOO = Foo()
    """
    with self.DepTree([("foo.py", foo)]):
      self.Check("""
        import foo
        print(foo.Bar.FOO)
      """)


if __name__ == "__main__":
  test_base.main()
