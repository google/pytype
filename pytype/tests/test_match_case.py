"""Tests for the match-case statement newly introduced in python in 3.10."""

from pytype.tests import test_base
from pytype.tests import test_utils


@test_utils.skipBeforePy(
    (3, 10), "match case statements only introduced in python 3.10"
)
class MatchCaseTest(test_base.BaseTest):
  """Tests for matching match-case statements."""

  def test_match_case_with_classes(self):
    self.CheckWithErrors("""
      import dataclasses
      @dataclasses.dataclass(frozen=True)
      class A:
        a: str
      @dataclasses.dataclass(frozen=True)
      class B:
        b: int
      def test(x: bool) -> A | B:
        return A('a')
      match test(True):
        case A(a):     # This case statement should be type checked
          print(a + 1) # unsupported-operands
    """)


if __name__ == "__main__":
  test_base.main()
