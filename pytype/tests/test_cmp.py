"""Test comparison operators."""

import os
import unittest

from pytype.tests import test_inference


class InTest(test_inference.InferenceTest):
  """Test for "x in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty = self.Infer("""
          def f(x, y):
            return x in y
          f(1, [1])
          f(1, [2])
          f("x", "x")
          f("y", "x")
          f("y", (1,))
          f("y", object())
      """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x in y
    """, deep=True, solve_unknowns=True, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  @unittest.skip("typegraphvm.cmp_in needs overloading support.")
  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() in []
      def g():
        return 3 in Foo()
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertOnlyHasReturnType(ty.Lookup("g"), self.complex)


class NotInTest(test_inference.InferenceTest):
  """Test for "x not in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty = self.Infer(srccode="""
      def f(x, y):
        return x not in y
      f(1, [1])
      f(1, [2])
      f("x", "x")
      f("y", "x")
      f("y", (1,))
      f("y", object())
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

# "not in" maps to the inverse of __contains__
  @unittest.skip("typegraphvm.cmp_not_in needs overloading support.")
  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() not in []
      def g():
        return 3 not in Foo()
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertOnlyHasReturnType(ty.Lookup("g"), self.complex)


class IsTest(test_inference.InferenceTest):
  """Test for "x is y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
      f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class IsNotTest(test_inference.InferenceTest):
  """Test for "x is not y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is not y
      f(1, 2)
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class LtTest(test_inference.InferenceTest):
  """Test for "x < y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x < y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __lt__(self, x):
          return 3j
      def f():
        return Foo() < 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  @unittest.skip("Needs full emulation of Objects/object.c:try_rich_compare""")
  def test_reverse(self):
    ty = self.Infer("""
      class Foo(object):
        def __lt__(self, x):
          return 3j
        def __gt__(self, x):
          raise x
      class Bar(Foo):
        def __gt__(self, x):
          return (3,)
      def f1():
        return Foo() < 3
      def f2():
        return Foo() < Foo()
      def f3():
        return Foo() < Bar()
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f1"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f2"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f3"), self.tuple)


class LeTest(test_inference.InferenceTest):
  """Test for "x <= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x <= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __le__(self, x):
          return 3j
      def f():
        return Foo() <= 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GtTest(test_inference.InferenceTest):
  """Test for "x > y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x > y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __gt__(self, x):
          return 3j
      def f():
        return Foo() > 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GeTest(test_inference.InferenceTest):
  """Test for "x >= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x >= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ge__(self, x):
          return 3j
      def f():
        return Foo() >= 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class EqTest(test_inference.InferenceTest):
  """Test for "x == y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x == y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __eq__(self, x):
          return 3j
      def f():
        return Foo() == 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)

  def test_class(self):
    ty = self.Infer("""
      def f(x, y):
        return x.__class__ == y.__class__
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class NeTest(test_inference.InferenceTest):
  """Test for "x != y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x != y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ne__(self, x):
          return 3j
      def f():
        return Foo() != 3
    """, deep=True, solve_unknowns=False, extract_locals=False)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class InstanceUnequalityTest(test_inference.InferenceTest):


  def test_is(self):
    """SomeType is not be the same as AnotherType."""
    self.assertNoErrors("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is None:
          return x
        else:
          return None
      """)


if __name__ == "__main__":
  test_inference.main()
