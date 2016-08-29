"""Tests for super()."""

from pytype.tests import test_inference


class SuperTest(test_inference.InferenceTest):
  """Tests for super()."""

  def testSetAttr(self):
    self.assertNoErrors("""
      class Foo(object):
        def foo(self, name, value):
          super(Foo, self).__setattr__(name, value)
    """)


if __name__ == "__main__":
  test_inference.main()
