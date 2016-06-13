"""Python 3 tests for Byterun."""

import os

from pytype.tests import test_inference


class TestPython3(test_inference.InferenceTest):
  """Tests for Python 3 compatiblity."""

  PYTHON_VERSION = (3, 4)

  def test_make_function(self):
    # TODO(dbaum): Ideally we should check that the annotations/defaults
    # are correctly processed once support for them is added.  It would
    # also be nice to verify that the correct number of items have been
    # popped from the stack.
    ty = self.Infer("""
      def uses_annotations(x: int) -> int:
        return 3

      def uses_pos_defaults(x, y=1):
        return 3

      def uses_kw_defaults(x, *args, y=1):
        return 3
    """) as ty:
      self.assertTypesMatchPytd(ty, """
        def uses_annotations(x: int) -> int
        def uses_kw_defaults(x) -> ?
        def uses_pos_defaults(x, ...) -> ?
      """)

  def test_make_class(self):
    with self.Infer("""
      class Thing(tuple):
        def __init__(self, x):
          self.x = x
      def f():
        x = Thing(1)
        x.y = 3
        return x
    """, deep=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Thing(Tuple[Any, ...]):
        x = ...  # type: Any
        y = ...  # type: int
        def __init__(self, x) -> NoneType: ...
      def f() -> Thing: ...
      """)

  def test_class_kwargs(self):
    with self.Infer("""
      # x, y are passed to type() or the metaclass. We currently ignore them.
      class Thing(x=True, y="foo"): pass
    """, deep=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
      class Thing: ...
      """)

  def test_exceptions(self):
    with self.Infer("""
      def f():
        try:
          raise ValueError()  # exercise byte_RAISE_VARARGS
        except ValueError as e:
          x = "s"
        finally:  # exercise byte_POP_EXCEPT
          x = 3
        return x
    """, deep=True, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f() -> int
      """)


if __name__ == "__main__":
  test_inference.main()
