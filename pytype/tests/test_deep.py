"""Tests for --deep."""

import unittest

from pytype.tests import test_inference


class StructuralTest(test_inference.InferenceTest):
  """Tests for running with --structural (NOT: --api)."""

  def testIntReturn(self):
    with self.Infer("""
      def f(x):
        return 1
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  @unittest.skip("Flawed test: i could be a slice")
  def testListUnknownIndex(self):
    with self.Infer("""
      def f(x, i):
        l = list([1, x])
        return l[i]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)
      # TODO(pludemann): verify the types of x, i

  @unittest.skip("Flawed test: i could be a slice")
  def testListUnknownIndexBothTypes(self):
    with self.Infer("""
      def f(i):
        l = list([1, "str"])
        return l[i]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasAllReturnTypes(ty.Lookup("f"), [self.int, self.str])

  def testIter(self):
    with self.Infer("""
      def f(x, y):
        for v in [x, y, 1]:
          return v
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testCallUnknown(self):
    with self.Infer("""
      def f(x):
        return x() or 1
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testCallBuiltin(self):
    with self.Infer("""
      def f(x):
        return repr(x)
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.str)

  def testAdd(self):
    # smoke test
    with self.Infer("""
      def f(x):
        x += 1
        return x
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTrue(ty.Lookup("f"))

  def testAddInt(self):
    # This one works, but depends on int.__radd__
    with self.Infer("""
      def f(x):
        return x + 1
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testIdentity(self):
    with self.Infer("""
      def f(x):
        return x
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testClassAttribute(self):
    with self.Infer("""
      class A(object):
        def __init__(self, x):
          self.x = x
      def f(x):
        a = A(x)
        return a.x
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  @unittest.skip("Flawed test: x could be a slice")
  def testFunctionPointer(self):
    with self.Infer("""
      def return_first(x, y):
        return x
      def return_second(x, y):
        return y
      def f(x):
        l = [return_first, return_second]
        return l[x](x, x)
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testListOfLists(self):
    with self.Infer("""
      def f(x):
        l = [[[x]], 0]
        return l[0][0][0]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryKeys(self):
    with self.Infer("""
      def f(x):
        d = {x: 1}
        return d.keys()[0]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryValues(self):
    with self.Infer("""
      def f(x):
        d = {1: x}
        return d.values()[0]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryLookup(self):
    with self.Infer("""
      def f(x):
        d = {0: x}
        return d[0]
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testClosure(self):
    with self.Infer("""
      def f(x):
        y = lambda: x
        return y()
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertIsIdentity(ty.Lookup("f"))

  def testUnknownBaseClass(self):
    with self.Infer("""
      def f(x):
        class A(x):
          pass
        a = A()
        a.x = 3
        return a.x
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testConstructorReturn(self):
    with self.Infer("""
      class Foo(object):
        def __init__(self, y, x=None):
          if x:
            x = list(x)

      def f(self):
        return Foo(3)
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      constructor = ty.Lookup("Foo").Lookup("__init__")
      self.assertOnlyHasReturnType(constructor, self.none_type)

  def testCallInClassWithClosure(self):
    with self.Infer("""
      def f():
        x = 3
        def inner(self):
          return x
        return inner
      class MyClass(object):
        attr = f()
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      cls = ty.Lookup("MyClass")
      method = cls.Lookup("attr")
      self.assertOnlyHasReturnType(method, self.int)

  def testStaticMethodWithSelf(self):
    with self.Infer("""
      class MyClass(object):
        def __init__(self, value):
          self.static_method(value)

        @staticmethod
        def static_method(value):
          return None
    """, deep=True, solve_unknowns=False, extract_locals=False) as ty:
      # Only do a smoke test. We don't have support for static methods in pytd.
      unused_cls = ty.Lookup("MyClass")

  def testUniqueReturn(self):
    with self.Infer("""
      def f(x, y):
        return issubclass(x, y)
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x, y) -> bool
      """)

  def testSlices(self):
    with self.Infer("""
      def trim(docstring):
        lines = docstring.splitlines()
        for line in lines[1:]:
          len(line)
        return lines
    """, deep=True, solve_unknowns=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def trim(docstring: bytearray or bytes or str or unicode) -> list[bytearray or str or unicode]
      """)

  def testAmbiguousTopLevelIdentifier(self):
    with self.Infer("""
      # from textwrap.py
      try:
          _unicode = unicode
      except NameError:
          class _unicode(object):
              pass
    """, deep=True, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        _unicode = ...  # type: type
      """)

if __name__ == "__main__":
  test_inference.main()
