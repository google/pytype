"""Tests for super()."""

from pytype.tests import test_base


class SuperTest(test_base.TargetPython27FeatureTest):
  """Tests for super()."""

  def test_super_missing_arg(self):
    # Python 2 super call does not implicitly infer the class and self
    # arguments. At least the class argument should be specified.
    _, errors = self.InferWithErrors("""
      class Foo(object):
        def __new__(cls):
          return super(cls).__new__(cls)  # wrong-arg-types[e1]
      class Bar(object):
        def __new__(cls):
          return super().__new__(cls)  # wrong-arg-count[e2]
    """)
    self.assertErrorRegexes(
        errors, {"e1": r"Type\[super\].*Type\[Foo\]", "e2": r"2.*0"})


test_base.main(globals(), __name__ == "__main__")
