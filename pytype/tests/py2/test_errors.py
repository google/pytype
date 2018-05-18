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


test_base.main(globals(), __name__ == "__main__")
