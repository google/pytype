"""Python 3 tests for Byterun."""

from pytype.tests import test_inference


class TestFunctions(test_inference.InferenceTest):

  PYTHON_VERSION = (3, 4)

  def test_make_function(self):
    # TODO(dbaum): Ideally we should check that the annotations/defaults
    # are correctly processed once support for them is added.  It would
    # also be nice to verify that the correct number of items have been
    # popped from the stack.
    with self.Infer("""
      def uses_annotations(x: int) -> int:
        return 3

      def uses_pos_defaults(x, y=1):
        return 3

      def uses_kw_defaults(x, *args, y=1):
        return 3
    """, run_builtins=False) as ty:
      self.assertTypesMatchPytd(ty, """
        def uses_annotations(x) -> ?
        def uses_kw_defaults(x) -> ?
        def uses_pos_defaults(x, y, ...) -> ?
      """)


if __name__ == "__main__":
  test_inference.main()
