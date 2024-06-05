"""Tests for @abc.abstractmethod in abc_overlay.py."""

from pytype.tests import test_base
from pytype.tests import test_utils


class AbstractMethodTests(test_base.BaseTest):
  """Tests for @abc.abstractmethod."""

  def test_instantiate_pyi_abstract_class(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class Example(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self) -> None: ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.Example()  # not-instantiable[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.Example.*foo"})

  def test_stray_abstractmethod(self):
    _, errors = self.InferWithErrors("""
      import abc
      class Example:  # ignored-abstractmethod[e]
        @abc.abstractmethod
        def foo(self):
          pass
    """)
    self.assertErrorRegexes(errors, {"e": r"foo.*Example"})

  def test_multiple_inheritance_implementation_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class Interface(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self): ...
        class X(Interface): ...
        class Implementation(Interface):
          def foo(self) -> int: ...
        class Foo(X, Implementation): ...
      """)
      self.Check("""
        import foo
        foo.Foo().foo()
      """, pythonpath=[d.path])

  def test_multiple_inheritance_error_pyi(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        import abc
        class X: ...
        class Interface(metaclass=abc.ABCMeta):
          @abc.abstractmethod
          def foo(self): ...
        class Foo(X, Interface): ...
      """)
      _, errors = self.InferWithErrors("""
        import foo
        foo.Foo().foo()  # not-instantiable[e]
      """, pythonpath=[d.path])
      self.assertErrorRegexes(errors, {"e": r"foo\.Foo.*foo"})

  def test_abc_metaclass_from_decorator(self):
    with test_utils.Tempdir() as d:
      d.create_file("six.pyi", """
        from typing import TypeVar, Callable
        T = TypeVar('T')
        def add_metaclass(metaclass: type) -> Callable[[T], T]: ...
      """)
      self.Check("""
        import abc
        import six
        @six.add_metaclass(abc.ABCMeta)
        class Foo:
          @abc.abstractmethod
          def foo(self):
            pass
      """, pythonpath=[d.path])

  def test_abc_child_metaclass(self):
    with test_utils.Tempdir() as d:
      d.create_file("six.pyi", """
        from typing import TypeVar, Callable
        T = TypeVar('T')
        def add_metaclass(metaclass: type) -> Callable[[T], T]: ...
      """)
      self.Check("""
        import abc
        import six
        class ABCChild(abc.ABCMeta):
          pass
        @six.add_metaclass(ABCChild)
        class Foo:
          @abc.abstractmethod
          def foo(self):
            pass
      """, pythonpath=[d.path])

  def test_misplaced_abstractproperty(self):
    _, errors = self.InferWithErrors("""
      import abc
      @abc.abstractproperty
      class Example:
        pass
      Example()  # not-callable[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"'abstractproperty' object"})


if __name__ == "__main__":
  test_base.main()
