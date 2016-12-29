"""Tests for the analysis phase matcher (match_var_against_type)."""


from pytype import utils
from pytype.tests import test_inference


class MatchTest(test_inference.InferenceTest):
  """Tests for matching types."""

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import tokenize
      import StringIO
      x = tokenize.generate_tokens(StringIO.StringIO("").readline)
    """, deep=True, solve_unknowns=False)
    self.assertTypesMatchPytd(ty, """
      tokenize = ...  # type: module
      StringIO = ...  # type: module
      x = ...  # type: Generator[Tuple[int, str, Tuple[int, int], Tuple[int, int], str], None, None]
    """)

  def testTypeAgainstCallable(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        def f(x: Callable) -> str
      """)
      ty = self.Infer("""
        import foo
        def f():
          return foo.f(int)
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        foo = ...  # type: module
        def f() -> str
      """)

  def testMatchUnknownAgainstContainer(self):
    ty = self.Infer("""
      a = {1}
      def f(x):
        return a & x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: Set[int]

      def f(x: Iterable) -> set: ...
    """)

  def testMatchStatic(self):
    ty = self.Infer("""
      s = {1}
      def f(x):
        # set.intersection is a static method:
        return s.intersection(x)
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      s = ...  # type: Set[int]

      def f(x) -> set: ...
    """)

  def testGenericHierarchy(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        def f(x: Iterable[str]) -> str
      """)
      ty = self.Infer("""
        import a
        x = a.f(["a", "b", "c"])
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)

  def testEmpty(self):
    ty = self.Infer("""
      a = []
      b = ["%d" % i for i in a]
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      a = ...  # type: List[nothing]
      b = ...  # type: List[str]
      i = ...  # type: Any
    """)

  def testGeneric(self):
    with utils.Tempdir() as d:
      d.create_file("a.pyi", """
        K = TypeVar("K")
        V = TypeVar("V")
        Q = TypeVar("Q")
        class A(Iterable[V], Generic[K, V]): ...
        class B(A[K, V]):
          def __init__(self):
            self := B[bool, str]
        def f(x: Iterable[Q]) -> Q
      """)
      ty = self.Infer("""
        import a
        x = a.f(a.B())
      """, pythonpath=[d.path], solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        a = ...  # type: module
        x = ...  # type: str
      """)


if __name__ == "__main__":
  test_inference.main()
