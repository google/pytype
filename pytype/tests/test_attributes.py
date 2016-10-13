"""Test instance and class attributes."""

import unittest

from pytype.tests import test_inference


class TestAttributes(test_inference.InferenceTest):
  """Tests for attributes."""

  def testSimpleAttribute(self):
    ty = self.Infer("""
      class A(object):
        def method1(self):
          self.a = 3
        def method2(self):
          self.a = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        a = ...  # type: complex or int
        def method1(self) -> NoneType
        def method2(self) -> NoneType
    """)

  def testOutsideAttributeAccess(self):
    ty = self.Infer("""
      class A(object):
        pass
      def f1():
        A().a = 3
      def f2():
        A().a = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        a = ...  # type: complex or int
      def f1() -> NoneType
      def f2() -> NoneType
    """)

  def testPrivate(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self._x = 3
        def foo(self):
          return self._x
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        _x = ...  # type: int
        def foo(self) -> int
    """)

  def testPublic(self):
    ty = self.Infer("""
      class C(object):
        def __init__(self):
          self.x = 3
        def foo(self):
          return self.x
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class C(object):
        x = ...  # type: int
        def foo(self) -> int
    """)

  def testCrosswise(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self):
          if id(self):
            self.b = B()
        def set_on_b(self):
          self.b.x = 3
      class B(object):
        def __init__(self):
          if id(self):
            self.a = A()
        def set_on_a(self):
          self.a.x = 3j
    """, deep=True, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        b = ...  # type: B
        x = ...  # type: complex
        def set_on_b(self) -> NoneType
      class B(object):
        a = ...  # type: A
        x = ...  # type: int
        def set_on_a(self) -> NoneType
    """)

  @unittest.skip("flaky?")
  def testAttrWithBadGetAttr(self):
    self.assertNoErrors("""
      class AttrA(object):
        def __getattr__(self, name2):
          pass
      class AttrB(object):
        def __getattr__(self):
          pass
      class AttrC(object):
        def __getattr__(self, x, y):
          pass
      class Foo(object):
        A = AttrA
        B = AttrB
        C = AttrC
        def foo(self):
          self.A
          self.B
          self.C
    """)

  def testGetters(self):
    ty = self.Infer("""
      class MyClass1(object):
        def __getattribute__(self, name):
          return super(MyClass1, self).__getattribute__(name)

      class MyClass2(object):
        def __getattribute__(self, name):
          return object.__getattribute__(self, name)

      class MyClass3(object):
        def __getattr__(self, name):
          return super(MyClass3, self).__getattr__(name)

      class MyClass4(object):
        def __getattr__(self, name):
          return object.__getattr__(self, name)
    """)
    self.assertTypesMatchPytd(ty, """
      class MyClass1(object): pass
      class MyClass2(object): pass
      class MyClass3(object): pass
      class MyClass4(object): pass
    """)

  def testGetAttribute(self):
    ty = self.Infer("""
      class A(object):
        def __getattribute__(self, name):
          return 42
      a = A()
      a.x = "hello world"
      x = a.x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
        def __getattribute__(self, name) -> int
      a = ...  # type: A
      x = ...  # type: int
    """)

  def testGetAttributeBranch(self):
    ty = self.Infer("""
      class A(object):
        x = "hello world"
      class B(object):
        def __getattribute__(self, name):
          return False
      def f(x):
        v = A()
        if x:
          v.__class__ = B
        return v.x
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      class A(object):
        x = ...  # type: str
      class B(object):
        def __getattribute__(self, name) -> bool
      def f(x) -> str or bool
    """)

  def testSetClass(self):
    ty = self.Infer("""
      def f(x):
        y = None
        y.__class__ = x.__class__
        return set([x, y])
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> set
    """)


if __name__ == "__main__":
  test_inference.main()
