"""Tests for classes, MROs, inheritance etc."""
import unittest

from pytype.pytd import pytd
from pytype.tests import test_inference


class InheritanceTest(test_inference.InferenceTest):
  """Tests for class inheritance."""

  @unittest.skip("needs (re-)analyzing methods on subclasses")
  def testSubclassAttributes(self):
    ty = self.Infer("""
      class Base(object):
        def get_lineno(self):
          return self.lineno
      class Leaf(Base):
        lineno = 0
    """, deep=True, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      class Base:
        pass
      class Leaf(Base):
        lineno: int
        def get_lineno(self) -> int
    """)

  def testClassAttributes(self):
    ty = self.Infer("""
      class A(object):
        pass
      class B(A):
        pass
      A.x = 3
      A.y = 3
      B.x = "foo"
      def ax():
        return A.x
      def bx():
        return B.x
      def ay():
        return A.y
      def by():
        return A.y
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("ax"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("bx"), self.str)
    self.assertOnlyHasReturnType(ty.Lookup("ay"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("by"), self.int)

  def testMultipleInheritance(self):
    ty = self.Infer("""
      class A(object):
        x = 1
      class B(A):
        y = 4
      class C(A):
        y = "str"
        z = 3j
      class D(B, C):
        pass
      def x():
        return D.x
      def y():
        return D.y
      def z():
        return D.z
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("x"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("y"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("z"), self.complex)

  def testInheritFromBuiltins(self):
    ty = self.Infer("""
      class MyDict(dict):
        def __init__(self):
          dict.__setitem__(self, "abc", "foo")

      def f():
        return MyDict()
      f()
    """, deep=False, show_library_calls=True)
    mydict = ty.Lookup("MyDict")
    self.assertOnlyHasReturnType(ty.Lookup("f"),
                                 pytd.ClassType("MyDict", mydict))

  def testInheritMethodsFromObject(self):
    # Test that even in the presence of multi-level inheritance,
    # we can still see attributes from "object".
    ty = self.Infer("""
      class A(object):
        pass
      class B(A):
        pass
      def f():
        return A().__sizeof__()
      def g():
        return B().__sizeof__()
      def h():
        return "bla".__sizeof__()
      f(); g(); h()
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("g"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("h"), self.int)

  def testMRO(self):
    ty = self.Infer("""
      class A(object):
        def a(self):
          return 1
      class B(A):
        def b(self):
          return 1.0
      class C(A):
        def b(self):
          # ignored in D, B.b has precedence
          return "foo"
      class D(B, C):
        pass
      def f():
        return A().a()
      def g():
        return B().b()
      def h():
        return C().b()
      def i():
        return D().b()
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.int)
    self.assertOnlyHasReturnType(ty.Lookup("g"), self.float)
    self.assertOnlyHasReturnType(ty.Lookup("h"), self.str)
    self.assertOnlyHasReturnType(ty.Lookup("i"), self.float)

if __name__ == "__main__":
  test_inference.main()
