"""Tests for collections.abc."""

from pytype.tests import test_base
from pytype.tests import test_utils


class CollectionsABCTest(test_base.BaseTest):
  """Tests for collections.abc."""

  def test_mapping(self):
    self.Check("""
      import collections
      class Foo(collections.abc.Mapping):
        pass
    """)

  def test_bytestring(self):
    """Check that we handle type aliases."""
    self.Check("""
      import collections
      x: collections.abc.ByteString
    """)

  def test_callable(self):
    ty = self.Infer("""
      from collections.abc import Callable
      f: Callable[[str], str] = lambda x: x
    """)
    # TODO(mdemello): We should ideally not be reexporting the "Callable" type,
    # and if we do it should be `Callable: type[typing.Callable]`.
    self.assertTypesMatchPytd(ty, """
      import typing
      Callable: type
      f: typing.Callable[[str], str]
    """)

  def test_pyi_callable(self):
    with test_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from collections.abc import Callable
        def f() -> Callable[[], float]: ...
      """)
      ty, _ = self.InferWithErrors("""
        import foo
        func = foo.f()
        func(0.0)  # wrong-arg-count
        x = func()
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        import foo
        from typing import Callable
        func: Callable[[], float]
        x: float
      """)

  def test_generator(self):
    self.Check("""
      from collections.abc import Generator
      def f() -> Generator[int, None, None]:
        yield 0
    """)

  def test_set(self):
    # collections.abc.Set is an alias for typing.AbstractSet.
    self.Check("""
      from collections.abc import Set
      def f() -> Set[int]:
        return frozenset([0])
    """)


if __name__ == "__main__":
  test_base.main()
