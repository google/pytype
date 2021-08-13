"""Tests for matching against protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""

from pytype import file_utils
from pytype.pytd import pytd_utils
from pytype.tests import test_base


class ProtocolTest(test_base.TargetIndependentTest):
  """Tests for protocol implementation."""

  def test_use_iterable(self):
    ty = self.Infer("""
      class A:
        def __iter__(self):
          return iter(__any_object__)
      v = list(A())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A:
        def __iter__(self) -> Any: ...
      v = ...  # type: list
    """)

  def test_generic(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, Protocol, TypeVar
        T = TypeVar("T")
        class Foo(Protocol[T]): ...
      """)
      self.Check("""
        import foo
      """, pythonpath=[d.path])

  def test_generic_py(self):
    ty = self.Infer("""
      from typing import Protocol, TypeVar
      T = TypeVar("T")
      class Foo(Protocol[T]):
        pass
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generic, Protocol, TypeVar
      T = TypeVar("T")
      class Foo(Protocol, Generic[T]): ...
    """)

  def test_generic_alias(self):
    foo_ty = self.Infer("""
      from typing import Protocol, TypeVar
      T = TypeVar("T")
      Foo = Protocol[T]

      class Bar(Foo[T]):
        pass
    """)
    self.assertTypesMatchPytd(foo_ty, """
      from typing import Generic, Protocol, TypeVar
      T = TypeVar("T")
      Foo = Protocol[T]
      class Bar(Protocol, Generic[T]): ...
    """)
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", pytd_utils.Print(foo_ty))
      ty = self.Infer("""
        import foo
        from typing import TypeVar
        T = TypeVar('T')
        class Baz(foo.Foo[T]):
          pass
      """, pythonpath=[d.path])
    self.assertTypesMatchPytd(ty, """
      foo: module
      from typing import Generic, Protocol, TypeVar
      T = TypeVar('T')
      class Baz(Protocol, Generic[T]): ...
    """)

  def test_self_referential_protocol(self):
    # Some protocols use methods that return instances of the protocol, e.g.
    # Iterator's __next__ returns Iterator. Make sure that doesn't crash pytype.
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        _TElem = TypeVar("_TElem")
        _TIter = TypeVar("_TIter", bound=Iter)
        class Iter(Generic[_TElem]):
          def __init__(self): ...
          def next(self) -> _TElem: ...
          def __next__(self) -> _TElem: ...
          def __iter__(self) -> _TIter: ...
      """)
      self.Check("""
        import foo
        i = foo.Iter[int]()
        next(i)
      """, pythonpath=[d.path])

  def test_attribute(self):
    self.CheckWithErrors("""
      from typing import Protocol
      class Foo(Protocol):
        x = 0
      class Bar:
        x = 1
      class Baz:
        x = '2'
      def f(foo):
        # type: (Foo) -> None
        pass
      f(Bar())
      f(Baz())  # wrong-arg-types
    """)

  def test_pyi_protocol_in_typevar(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import Generic, TypeVar
        from typing_extensions import Protocol

        T = TypeVar('T', bound=SupportsClose)

        class SupportsClose(Protocol):
          def close(self) -> object: ...

        class Foo(Generic[T]):
          def __init__(self, x: T) -> None: ...
      """)
      self.Check("""
        import foo
        class Bar:
          def close(self) -> None:
            pass
        foo.Foo(Bar())
      """, pythonpath=[d.path])


test_base.main(globals(), __name__ == "__main__")
