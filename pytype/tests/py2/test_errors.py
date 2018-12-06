"""Tests for displaying errors."""

from pytype.tests import test_base


class ErrorTest(test_base.TargetPython27FeatureTest):
  """Tests for errors."""

  def testProtocolMismatch(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object): pass
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [
        (2, "wrong-arg-types", "__iter__, next")
    ])

  def testProtocolMismatchPartial(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __iter__(self):
          return self
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [(
        4, "wrong-arg-types", r"\n\s*next\s*$")])  # `next` on its own line

  def testGetSlice(self):
    errors = self.CheckWithErrors("def f(): v = []; return v[:'foo']")
    self.assertErrorLogIs(errors, [
        (1, "unsupported-operands",
         r"slicing.*List.*str.*__getslice__ on List.*Optional\[int\]")])


test_base.main(globals(), __name__ == "__main__")
