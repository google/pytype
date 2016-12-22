"""Tests for super()."""


from pytype import utils
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

  def testSuperType(self):
    ty = self.Infer("""
      class A(object):
        pass
      x = super(type, A)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        pass
      x = ...  # type: super
    """)

  def testSuperWithAmbiguousBase(self):
    with utils.Tempdir() as d:
      d.create_file("foo.pyi", """
        class Grandparent(object):
          def f(self) -> int
      """)
      ty = self.Infer("""
        import foo
        class Parent(foo.Grandparent):
          pass
        OtherParent = __any_object__
        class Child(OtherParent, Parent):
          def f(self):
            return super(Parent, self).f()
      """, pythonpath=[d.path], deep=True, solve_unknowns=True)
      self.assertTypesMatchPytd(ty, """
        from typing import Any
        foo = ...  # type: module
        class Parent(foo.Grandparent): ...
        OtherParent = ...  # type: Any
        class Child(Any, Parent): ...
      """)

  def testSuperWithAny(self):
    self.assertNoErrors("""
      super(__any_object__, __any_object__)
    """)


if __name__ == "__main__":
  test_inference.main()
