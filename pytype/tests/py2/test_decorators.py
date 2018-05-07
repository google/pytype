"""Test for function and class decorators."""

from pytype.tests import test_base


class DecoratorsTest(test_base.TargetPython27FeatureTest):
  """Tests for decorators."""

  def testAttributeErrorUnderClassDecorator(self):
    # This does not detect the error under target python3 (b/78591647)
    _, errors = self.InferWithErrors("""\
      def decorate(cls):
        return __any_object__
      @decorate
      class Foo(object):
        def Hello(self):
          return self.Goodbye()  # line 6
    """)
    self.assertErrorLogIs(errors, [(6, "attribute-error", r"Goodbye")])


if __name__ == "__main__":
  test_base.main()
