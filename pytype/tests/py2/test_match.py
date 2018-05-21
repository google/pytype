"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype import file_utils
from pytype.tests import test_base


class MatchTest(test_base.TargetPython27FeatureTest):
  """Tests for matching types."""

  # Forked into py2 and py3 versions

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Tuple
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)

  def testCallableAgainstGeneric(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        from typing import TypeVar, Callable, Generic, Iterable, Iterator
        A = TypeVar("A")
        N = TypeVar("N")
        class Foo(Generic[A]):
          def __init__(self, c: Callable[[], N]):
            self = Foo[N]
        x = ...  # type: Iterator[int]
      """)
      self.Check("""
        import foo
        foo.Foo(foo.x.next)
      """, pythonpath=[d.path])

  def testEmpty(self):
    ty = self.Infer("""
      a = []
      b = ["%d" % i for i in a]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, List
      a = ...  # type: List[nothing]
      b = ...  # type: List
      i = ...  # type: Any
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import tokenize
      import StringIO
      x = tokenize.generate_tokens(StringIO.StringIO("").readline)
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Generator, Tuple
      tokenize = ...  # type: module
      StringIO = ...  # type: module
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)


test_base.main(globals(), __name__ == "__main__")
