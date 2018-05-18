"""Tests for type comments."""

from pytype.tests import test_base


class FunctionCommentWithAnnotationsTest(test_base.TargetPython3BasicTest):
  """Tests for type comments that require annotations."""

  def testFunctionTypeCommentPlusAnnotations(self):
    _, errors = self.InferWithErrors("""\
            def foo(x: int) -> float:
        # type: (int) -> float
        return x
    """)
    self.assertErrorLogIs(errors, [(3, "redundant-function-type-comment")])

  def testListComprehensionComments(self):
    ty = self.Infer("""\
            from typing import List
      def f(x: str):
        pass
      def g(xs: List[str]) -> List[str]:
        ys = [f(x) for x in xs]  # type: List[str]
        return ys
    """)
    self.assertTypesMatchPytd(ty, """\
      from typing import List
      def f(x: str) -> None: ...
      def g(xs: List[str]) -> List[str]: ...
    """)


test_base.main(globals(), __name__ == "__main__")
