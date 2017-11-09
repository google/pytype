"""Test comparison operators."""

import unittest

from pytype.tests import test_base


class InTest(test_base.BaseTest):
  """Test for "x in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty, errors = self.InferWithErrors("""\
      def f(x, y):
        return x in y
      f(1, [1])
      f(1, [2])
      f("x", "x")
      f("y", "x")
      f("y", (1,))
      f("y", object())
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"__contains__.*object")])

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x in y
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 in Foo()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __contains__(self, x) -> complex
      def f() -> bool
      def g() -> bool
    """)

  def test_none(self):
    _, errors = self.InferWithErrors("""\
      x = None
      if "" in x:
        del x[""]
    """)
    self.assertErrorLogIs(errors, [(2, "none-attr",
                                    r"__contains__.*None"),
                                   (3, "none-attr", r"__delitem__.*None")])


class NotInTest(test_base.BaseTest):
  """Test for "x not in y". Also test overloading of this operator."""

  def test_concrete(self):
    ty, errors = self.InferWithErrors("""\
      def f(x, y):
        return x not in y
      f(1, [1])
      f(1, [2])
      f("x", "x")
      f("y", "x")
      f("y", (1,))
      f("y", object())
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)
    self.assertErrorLogIs(errors, [(2, "unsupported-operands",
                                    r"__contains__.*object")])

  # "not in" maps to the inverse of __contains__
  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __contains__(self, x):
          return 3j
      def f():
        return Foo() not in []
      def g():
        # The result of __contains__ is coerced to a bool.
        return 3 not in Foo()
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        def __contains__(self, x) -> complex
      def f() -> bool
      def g() -> bool
    """)

  def test_none(self):
    _, errors = self.InferWithErrors("""\
      x = None
      if "" not in x:
        x[""] = 42
    """)
    self.assertErrorLogIs(errors, [(2, "none-attr",
                                    r"__contains__.*None"),
                                   (3, "none-attr", r"__setitem__.*None")])


class IsTest(test_base.BaseTest):
  """Test for "x is y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class IsNotTest(test_base.BaseTest):
  """Test for "x is not y". This operator can't be overloaded."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x is not y
      f(1, 2)
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_deep(self):
    ty = self.Infer("""
      def f(x, y):
        return x is y
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)


class LtTest(test_base.BaseTest):
  """Test for "x < y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x < y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __lt__(self, x):
          return 3j
      def f():
        return Foo() < 3
    """, deep=True, show_library_calls=True)
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
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f1"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f2"), self.complex)
    self.assertOnlyHasReturnType(ty.Lookup("f3"), self.tuple)


class LeTest(test_base.BaseTest):
  """Test for "x <= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x <= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __le__(self, x):
          return 3j
      def f():
        return Foo() <= 3
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GtTest(test_base.BaseTest):
  """Test for "x > y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x > y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __gt__(self, x):
          return 3j
      def f():
        return Foo() > 3
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class GeTest(test_base.BaseTest):
  """Test for "x >= y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x >= y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ge__(self, x):
          return 3j
      def f():
        return Foo() >= 3
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class EqTest(test_base.BaseTest):
  """Test for "x == y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x == y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __eq__(self, x):
          return 3j
      def f():
        return Foo() == 3
    """, deep=True, show_library_calls=True)
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

  def test_primitive_against_unknown(self):
    self.assertNoCrash(self.Check, """
      v = None  # type: int
      v == __any_object__
    """)


class NeTest(test_base.BaseTest):
  """Test for "x != y". Also test overloading."""

  def test_concrete(self):
    ty = self.Infer("""
      def f(x, y):
        return x != y
      f(1, 2)
      f(1, "a")
      f(object(), "x")
    """, deep=False, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.bool)

  def test_overloaded(self):
    ty = self.Infer("""
      class Foo(object):
        def __ne__(self, x):
          return 3j
      def f():
        return Foo() != 3
    """, deep=True, show_library_calls=True)
    self.assertOnlyHasReturnType(ty.Lookup("f"), self.complex)


class InstanceUnequalityTest(test_base.BaseTest):

  def test_is(self):
    """SomeType is not be the same as AnotherType."""
    self.Check("""
      from __future__ import google_type_annotations
      from typing import Optional
      def f(x: Optional[str]) -> NoneType:
        if x is None:
          return x
        else:
          return None
      """)

  def testIteratorContains(self):
    self.Check("""
      1 in iter((1, 2))
      1 not in iter((1, 2))
    """)


if __name__ == "__main__":
  test_base.main()
