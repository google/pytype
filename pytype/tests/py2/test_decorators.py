"""Test for function and class decorators."""

from pytype.tests import test_base


class DecoratorsTest(test_base.TargetPython27FeatureTest):
  """Tests for decorators."""

  def test_attribute_error_under_class_decorator(self):
    # This does not detect the error under target python3 (b/78591647)
    _, errors = self.InferWithErrors("""
      def decorate(cls):
        return __any_object__
      @decorate
      class Foo(object):
        def Hello(self):
          return self.Goodbye()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"Goodbye"})


test_base.main(globals(), __name__ == "__main__")
