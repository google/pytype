"""Tests for super()."""

from pytype.tests import test_base


class SuperTest(test_base.TargetPython27FeatureTest):
  """Tests for super()."""

  def testSuperMissingArg(self):
    # Python 2 super call does not implicitly infer the class and self
    # arguments. At least the class argument should be specified.
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __new__(cls):
          return super(cls).__new__(cls)
      class Bar(object):
        def __new__(cls):
          return super().__new__(cls)
    """)
    self.assertErrorLogIs(errors, [
        (3, "wrong-arg-types", r"Type\[super\].*Type\[Foo\]"),
        (6, "wrong-arg-count", r"2.*0")])


if __name__ == "__main__":
  test_base.main()
