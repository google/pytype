"""Tests for --deep."""

from pytype.tests import test_inference


class StructuralTest(test_inference.InferenceTest):
  """Tests for running with --structural (NOT: --api)."""

  def testIntReturn(self):
    ty = self.Infer("""
      def f(x):
        return 1
    """, deep=True, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testListUnknownIndex(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def f(x, i: int):
        l = list([1, x])
        return l[i]
    """, deep=True, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testListUnknownIndexBothTypes(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def f(i: int):
        l = list([1, "str"])
        return l[i]
    """, deep=True, show_library_calls=True)
    self.assertHasAllReturnTypes(ty.Lookup("f"), [self.int, self.str])

  def testIter(self):
    ty = self.Infer("""
      def f(x, y):
        for v in [x, y, 1]:
          return v
    """, deep=True, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testCallUnknown(self):
    ty = self.Infer("""
      def f(x):
        return x() or 1
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f(x) -> Any
    """)

  def testCallBuiltin(self):
    ty = self.Infer("""
      def f(x):
        return repr(x)
    """, deep=True, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.str)

  def testAdd(self):
    # smoke test
    ty = self.Infer("""
      def f(x):
        x += 1
        return x
    """, deep=True, show_library_calls=True)
    self.assertTrue(ty.Lookup("f"))

  def testAddInt(self):
    ty = self.Infer("""
      def f(x):
        return x + 1
    """, deep=True)
    self.assertHasReturnType(ty.Lookup("f"), self.anything)

  def testIdentity(self):
    ty = self.Infer("""
      def f(x):
        return x
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testClassAttribute(self):
    ty = self.Infer("""
      class A(object):
        def __init__(self, x):
          self.x = x
      def f(x):
        a = A(x)
        return a.x
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testFunctionPointer(self):
    ty = self.Infer("""
      from __future__ import google_type_annotations
      def return_first(x, y):
        return x
      def return_second(x, y):
        return y
      def f(x: int):
        l = [return_first, return_second]
        return l[x](x, x)
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testListOfLists(self):
    ty = self.Infer("""
      def f(x):
        l = [[[x]], 0]
        return l[0][0][0]
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryKeys(self):
    ty = self.Infer("""
      def f(x):
        d = {x: 1}
        return d.keys()[0]
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryValues(self):
    ty = self.Infer("""
      def f(x):
        d = {1: x}
        return d.values()[0]
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testDictionaryLookup(self):
    ty = self.Infer("""
      def f(x):
        d = {0: x}
        return d[0]
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testClosure(self):
    ty = self.Infer("""
      def f(x):
        y = lambda: x
        return y()
    """, deep=True, show_library_calls=True)
    self.assertIsIdentity(ty.Lookup("f"))

  def testUnknownBaseClass(self):
    ty = self.Infer("""
      def f(x):
        class A(x):
          pass
        a = A()
        a.x = 3
        return a.x
    """, deep=True, show_library_calls=True)
    self.assertHasReturnType(ty.Lookup("f"), self.int)

  def testConstructorReturn(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self, y, x=None):
          if x:
            x = list(x)

      def f(self):
        return Foo(3)
    """, deep=True, show_library_calls=True)
    constructor = ty.Lookup("Foo").Lookup("__init__")
    self.assertOnlyHasReturnType(constructor, self.none_type)

  def testCallInClassWithClosure(self):
    ty = self.Infer("""
      def f():
        x = 3
        def inner(self):
          return x
        return inner
      class MyClass(object):
        attr = f()
    """, deep=True, show_library_calls=True)
    cls = ty.Lookup("MyClass")
    method = cls.Lookup("attr")
    self.assertOnlyHasReturnType(method, self.int)

  def testStaticMethodWithSelf(self):
    ty = self.Infer("""
      class MyClass(object):
        def __init__(self, value):
          self.static_method(value)

        @staticmethod
        def static_method(value):
          return None
    """, deep=True, show_library_calls=True)
    # Only do a smoke test. We don't have support for static methods in pytd.
    unused_cls = ty.Lookup("MyClass")

  def testUniqueReturn(self):
    ty = self.Infer("""
      def f(x, y):
        return issubclass(x, y)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f(x, y) -> bool
    """)

  def testAmbiguousTopLevelIdentifier(self):
    ty = self.Infer("""
      # from textwrap.py
      try:
          _unicode = unicode
      except NameError:
          class _unicode(object):
              pass
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      _unicode = ...  # type: type
    """)

  def testCachingOfUnknowns(self):
    ty = self.Infer("""
      def f(a, b):
        a + b

      f(__any_object__, 1)
    """, deep=True)
    self.assertTypesMatchPytd(ty, """
      def f(a, b) -> None
    """)


if __name__ == "__main__":
  test_inference.main()
