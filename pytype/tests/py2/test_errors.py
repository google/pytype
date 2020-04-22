"""Tests for displaying errors."""

from pytype.tests import test_base


class ErrorTest(test_base.TargetPython27FeatureTest):
  """Tests for errors."""

  def test_protocol_mismatch(self):
    _, errors = self.InferWithErrors("""
      class Foo(object): pass
      next(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"__iter__, next"})

  def test_protocol_mismatch_partial(self):
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __iter__(self):
          return self
      next(Foo())  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(
        errors, {"e": r"\n\s*next\s*$"})  # `next` on its own line

  def test_getslice(self):
    errors = self.CheckWithErrors("""
      def f(): v = []; return v[:'foo']  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(
        errors,
        {"e": r"slicing.*List.*str.*__getslice__ on List.*Optional\[int\]"})


test_base.main(globals(), __name__ == "__main__")
