"""Tests for the analysis phase matcher (match_var_against_type)."""

from pytype.tests import test_inference


class MatchTest(test_inference.InferenceTest):

  def testCallable(self):
    with self.Infer("""
      import tokenize
      def f():
        pass
      x = tokenize.generate_tokens(f)
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        tokenize = ...  # type: module
        def f() -> NoneType
        x = ...  # type: Generator[Tuple[int, ...]]
      """)


if __name__ == "__main__":
  test_inference.main()
