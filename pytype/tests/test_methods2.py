"""Test methods."""

from pytype.tests import test_base
from pytype.tests import test_utils


class TestMethods(test_base.BaseTest):
  """Tests for class methods."""

  def test_function_init(self):
    ty = self.Infer("""
      def __init__(self: int):
        return self
    """)
    self.assertTypesMatchPytd(ty, """
      def __init__(self: int) -> int: ...
    """)

  def test_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __init__(x: int):
          pass  # invalid-annotation[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*x"})

  def test_late_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __init__(x: "X"):
          pass  # invalid-annotation[e]
      class X:
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"X.*x"})

  def test_attribute_with_annotated_self(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __init__(self: int):
          self.x = 3  # invalid-annotation[e]
        def foo(self):
          return self.x
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*self"})

  def test_attribute_with_annotated_self_and_function_init(self):
    errors = self.CheckWithErrors("""
      class Foo:
        def __init__(self: int):
          self.x = 3  # invalid-annotation[e]
      def __init__(self: int):
        pass
    """)
    self.assertErrorRegexes(errors, {"e": r"int.*self"})

  def test_use_abstract_classmethod(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc

        class Foo(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          @classmethod
          def foo(cls, value) -> int: ...
      """)
      self.Check("""
        import collections
        import foo

        class Bar:
          def __init__(self, **kwargs):
            for k, v in self.f().items():
              v.foo(kwargs[k])

          def f(self) -> collections.OrderedDict[str, foo.Foo]:
            return __any_object__
      """, pythonpath=[d.path])

  def test_max_depth(self):
    # pytype hits max depth in A.cmp() when trying to instantiate `other`,
    # leading to the FromInt() call in __init__ being skipped and pytype
    # thinking that other.x is an int. If max depth is raised, pytype correctly
    # sees that self.x will be a str, and no error is raised.
    self.CheckWithErrors("""
      from typing import Any, Union

      class A:
        def __init__(self, x: int):
          self.x = 1
          self.FromInt(x)

        def cmp(self, other: 'A') -> bool:
          return self.Upper() < other.Upper()

        def FromInt(self, x: int) -> None:
          self.x = 'x'

        def Upper(self) -> str:
          return self.x.upper()  # attribute-error
    """, maximum_depth=2)

  def test_call_dispatch(self):
    self.Check("""
      from typing import Union
      class Foo:
        def __call__(self):
          pass
      class Bar:
        def __call__(self, x):
          pass
      def f(x: Union[Foo, Bar]):
        if isinstance(x, Foo):
          return x()
    """)

  def test_lookup_on_dynamic_class(self):
    self.Check("""
      class Foo:
        _HAS_DYNAMIC_ATTRIBUTES = True
        def f(self) -> str:
          return ''
        def g(self):
          assert_type(self.f(), str)
    """)


class TestMethodsPy3(test_base.BaseTest):
  """Test python3-specific method features."""

  def test_init_subclass_classmethod(self):
    """__init_subclass__ should be promoted to a classmethod."""

    self.Check("""
      from typing import Type

      _REGISTERED_BUILDERS = {}

      class A():
        def __init_subclass__(cls, **kwargs):
          _REGISTERED_BUILDERS['name'] = cls

      def get_builder(name: str) -> Type[A]:
        return _REGISTERED_BUILDERS[name]
    """)

  def test_pass_through_typevar(self):
    self.Check("""
      from typing import TypeVar
      F = TypeVar('F')
      def f(x: F) -> F:
        return x
      class A:
        def f(self, x: float) -> float:
          return x
      g = f(A().f)
      assert_type(g(0), float)
    """)

  def test_dunder_self(self):
    self.Check("""
      from typing import Type
      class A:
        def foo(self):
          return 42

        @classmethod
        def bar(cls):
          return cls()

      a = A().foo.__self__
      b = A.bar.__self__
      assert_type(a, A)
      assert_type(b, Type[A])
    """)

  def test_signature_inference(self):
    ty = self.Infer("""
      class C:
        def __init__(self, fn1, fn2):
          self._fn1 = fn1
          self._fn2 = fn2
        def f(self, x):
          self._fn1(x)
          self._fn2(x=x)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class C:
        def __init__(self, fn1, fn2) -> None: ...
        def f(self, x) -> None: ...
        def _fn1(self, _1) -> Any: ...
        def _fn2(self, x) -> Any: ...
    """)


if __name__ == "__main__":
  test_base.main()
