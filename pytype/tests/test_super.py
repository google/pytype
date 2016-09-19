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

  def testGetAttr(self):
    self.assertNoErrors("""
      class Foo(object):
        def hello(self, name):
          getattr(super(Foo, self), name)
    """)

  def testGetAttrMultipleInheritance(self):
    self.assertNoErrors("""
      class X(object):
        pass

      class Y(object):
        bla = 123

      class Foo(X, Y):
        def hello(self):
          getattr(super(Foo, self), "bla")
    """)

  def testGetAttrInheritance(self):
    self.assertNoErrors("""
      class Y(object):
        bla = 123

      class Foo(Y):
        def hello(self):
          getattr(super(Foo, self), "bla")
    """)

  def testIsInstance(self):
    self.assertNoErrors("""
      class Y(object):
        pass

      class Foo(Y):
        def hello(self):
          return isinstance(super(Foo, self), Y)
    """)

  def testCallSuper(self):
    _, errorlog = self.InferAndCheck("""
      class Y(object):
        pass

      class Foo(Y):
        def hello(self):
          return super(Foo, self)()
    """)
    self.assertEquals(1, len(errorlog))
    self.assertErrorLogContains(errorlog, r"super.*\[not\-callable\]")


if __name__ == "__main__":
  test_inference.main()
