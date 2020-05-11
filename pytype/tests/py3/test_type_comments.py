"""Tests for type comments."""

from pytype.tests import test_base


class FunctionCommentWithAnnotationsTest(test_base.TargetPython3BasicTest):
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


class Py3TypeCommentTest(test_base.TargetPython3FeatureTest):

  def test_ignored_comment(self):
    self.CheckWithErrors("""
      def f():
        v: int = None  # type: str  # ignored-type-comment
    """)


test_base.main(globals(), __name__ == "__main__")
