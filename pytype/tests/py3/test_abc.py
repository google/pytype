"""Tests for @abc.abstractmethod in abc_overlay.py."""

from pytype import file_utils
from pytype.tests import test_base


class AbstractMethodTests(test_base.TargetPython3FeatureTest):
  """Tests for @abc.abstractmethod."""

  def test_no_skip_call(self):
    self.Check("""
      import abc
      class Example(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def foo(self) -> int:
          return None
    """, skip_repeat_calls=False)

  def test_multiple_inheritance_builtins(self):
    self.Check("""
      import abc
      class Foo(object, metaclass=abc.ABCMeta):
        pass
      class Bar1(Foo, tuple):
        pass
      class Bar2(Foo, bytes):
        pass
      class Bar3(Foo, str):
        pass
      class Bar4(Foo, bytearray):
        pass
      class Bar5(Foo, dict):
        pass
      class Bar6(Foo, list):
        pass
      class Bar7(Foo, set):
        pass
      class Bar8(Foo, frozenset):
        pass
      class Bar9(Foo, memoryview):
        pass
      class BarA(Foo, range):
        pass
      Bar1()
      Bar2()
      Bar3()
      Bar4()
      Bar5()
      Bar6()
      Bar7()
      Bar8()
      Bar9(b"")
      BarA(0)
    """)

  def test_abstractproperty(self):
    ty, errors = self.InferWithErrors("""
      import abc
      class Foo(metaclass=abc.ABCMeta):
        @abc.abstractproperty
        def foo(self):
          return 42
      class Bar(Foo):
        @property
        def foo(self):
          return super(Bar, self).foo
      v1 = Foo().foo  # not-instantiable[e]
      v2 = Bar().foo
    """)
    self.assertTypesMatchPytd(ty, """
      import abc
      from typing import Any
      abc = ...  # type: module
      v1 = ...  # type: Any
      v2 = ...  # type: int
      class Bar(Foo):
        foo = ...  # type: Any
      class Foo(metaclass=abc.ABCMeta):
        foo = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"Foo.*foo"})

  def test_dictviews(self):
    self.Check("""
      from collections import abc
      from typing import Dict
      d: Dict[str, int] = {}
      abc.ItemsView(d)
      abc.KeysView(d)
      abc.ValuesView(d)
    """)

  def test_instantiate_abstract_class_annotation(self):
    # When a function parameter is annotated as `Type[A]`, where A is abstract,
    # presumably the intent is for callers to pass in concrete subclasses of A,
    # so we should not raise an error if A is instantiated in the body.
    self.Check("""
      import abc
      from typing import Type
      class A(metaclass=abc.ABCMeta):
        @abc.abstractmethod
        def a(self):
          pass
      def f(x: Type[A]):
        return x()
    """)

  def test_instantiate_abstract_pytdclass_annotation(self):
    # When a function parameter is annotated as `Type[A]`, where A is abstract,
    # presumably the intent is for callers to pass in concrete subclasses of A,
    # so we should not raise an error if A is instantiated in the body.
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class A(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def a(self) -> None: ...
      """)
      self.Check("""
        import foo
        from typing import Type
        def f(x: Type[foo.A]):
          return x()
      """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
