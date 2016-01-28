"""Tests of selected stdlib functions."""


from pytype.tests import test_inference


class StdlibTests(test_inference.InferenceTest):

  def testAST(self):
    with self.Infer("""
      import ast
      def f():
        return ast.parse("True")
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        ast = ...  # type: module
        def f() -> _ast.AST
      """)


if __name__ == "__main__":
  test_inference.main()
