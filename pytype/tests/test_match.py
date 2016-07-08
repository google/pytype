"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype.tests import test_inference


class MatchTest(test_inference.InferenceTest):
  """Tests for matching types."""

  def testCallable(self):
    ty = self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      tokenize = ...  # type: module
      def f() -> NoneType
      x = ...  # type: Generator[Tuple[Union[Tuple[int, ...], int, str], ...]]
    """)

  def testBoundAgainstCallable(self):
    ty = self.Infer("""
      import tokenize
      import StringIO
      x = tokenize.generate_tokens(StringIO.StringIO("").readline)
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      tokenize = ...  # type: module
      StringIO = ...  # type: module
      x = ...  # type: Generator[Tuple[Union[Tuple[int, ...], int, str], ...]]
    """)

  def testMatchUnknownAgainstContainer(self):
    ty = self.Infer("""
      a = {1}
      def f(x):
        return a & x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      a = ...  # type: Set[int]

      def f(x: Set[Any]) -> Set[Any]: ...
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

      def f(x) -> Set[Any]: ...
    """)


if __name__ == "__main__":
  test_inference.main()
