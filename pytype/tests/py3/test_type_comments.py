"""Tests for type comments."""

from pytype.tests import test_base


class FunctionCommentWithAnnotationsTest(test_base.BaseTest):
  """Tests for type comments that require annotations."""

  def test_function_type_comment_plus_annotations(self):
    self.InferWithErrors("""
      def foo(x: int) -> float:
        # type: (int) -> float  # redundant-function-type-comment
        return x
    """)

  def test_list_comprehension_comments(self):
    ty, errors = self.InferWithErrors("""
      from typing import List
      def f(x: str):
        pass
      def g(xs: List[str]) -> List[str]:
        ys = [f(x) for x in xs]  # type: List[str]  # annotation-type-mismatch[e]
        return ys
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import List
      def f(x: str) -> None: ...
      def g(xs: List[str]) -> List[str]: ...
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Annotation: List\[str\].*Assignment: List\[None\]"})


class Py3TypeCommentTest(test_base.BaseTest):
  """Type comment tests that use Python 3-only features."""

  def test_ignored_comment(self):
    self.CheckWithErrors("""
      def f():
        v: int = None  # type: str  # ignored-type-comment
    """)

  def test_first_line_of_code(self):
    # In Python 3.8, the line number of this method's first opcode is the second
    # line in the method body, not the first. This test verifies that we are
    # still able to determine the first line number in the body. If we get the
    # wrong line, the `Dict[str, int]` annotation is associated to the method
    # signature, generating a spurious [redundant-function-type-comment] error.
    self.Check("""
      from typing import Dict
      def f() -> Dict[str, int]:
        # some_var = ''
        # something more
        cast_type: Dict[str, int] = {
          'one': 1,
          'two': 2,
          'three': 3,
        }
        return cast_type
    """)

if __name__ == "__main__":
  test_base.main()
