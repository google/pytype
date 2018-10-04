"""Tests for matching against protocols.

Based on PEP 544 https://www.python.org/dev/peps/pep-0544/.
"""


from pytype import file_utils
from pytype.tests import test_base


class ProtocolTest(test_base.TargetIndependentTest):
  """Tests for protocol implementation."""

  def test_use_iterable(self):
    ty = self.Infer("""
      class A(object):
        def __iter__(self):
          return iter(__any_object__)
      v = list(A())
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class A(object):
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


test_base.main(globals(), __name__ == "__main__")
