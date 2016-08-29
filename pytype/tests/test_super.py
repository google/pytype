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

  def testStr(self):
    self.assertNoErrors("""
      class Foo(object):
        def foo(self, name, value):
          super(Foo, self).__str__()
    """)

  def testGet(self):
    self.assertNoErrors("""
      class Foo(object):
        def foo(self, name, value):
          super(Foo, self).__get__(name)
    """)

  def testSet(self):
    self.assertNoErrors("""
      class Foo(object):
        def foo(self, name, value):
          super(Foo, self).__set__(name, value)
    """)

  def testInit(self):
    self.assertNoErrors("""
      class Foo(object):
        def foo(self, name, value):
          super(Foo, self).__init__()
    """)


if __name__ == "__main__":
  test_inference.main()
