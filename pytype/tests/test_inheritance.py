"""Tests for classes, MROs, inheritance etc."""
import unittest

from pytype.pytd import pytd
from pytype.tests import test_inference


class InheritanceTest(test_inference.InferenceTest):
  """Tests for class inheritance."""

  @unittest.skip("needs analyzing methods on subclasses")
  def testSubclassAttributes(self):
    with self.Infer("""
      class Base(object):
        def get_lineno(self):
          return self.lineno
      class Leaf(Base):
        lineno = 0
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        class Base:
          pass
        class Leaf:
          def get_lineno(self) -> int
      """)

  def testClassAttributes(self):
    with self.Infer("""
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
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("ax"), self.int)
      self.assertOnlyHasReturnType(ty.Lookup("bx"), self.str)
      self.assertOnlyHasReturnType(ty.Lookup("ay"), self.int)
      self.assertOnlyHasReturnType(ty.Lookup("by"), self.int)

  def testMultipleInheritance(self):
    with self.Infer("""
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
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertOnlyHasReturnType(ty.Lookup("x"), self.int)
      self.assertOnlyHasReturnType(ty.Lookup("y"), self.int)
      self.assertOnlyHasReturnType(ty.Lookup("z"), self.complex)

  @unittest.skip("Needs type parameters on inherited classes.")
  def testInheritFromBuiltins(self):
    with self.Infer("""
      class MyDict(dict):
        def __init__(self):
          dict.__setitem__(self, "abc", "foo")

      def f():
        return NoCaseKeysDict()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      mydict = ty.Lookup("MyDict")
      self.assertOnlyHasReturnType(ty.Lookup("f"),
                                   pytd.ClassType("MyDict", mydict))


if __name__ == "__main__":
  test_inference.main()
